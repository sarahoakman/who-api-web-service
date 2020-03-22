# -*- coding: utf-8 -*-
import scrapy
import re
import json
from collections import Counter
from text2digits import text2digits #need to pip install
from bs4 import BeautifulSoup
from urllib.request import urlopen
import string
import pycountry
#from Location import * this doesnt work with scrapy?
from geotext import GeoText
import unicodedata
from who_scraper.items import *
import pytz

class ReportbotSpider(scrapy.Spider):
    name = 'reportbot'
    #start_urls = ['https://www.who.int/csr/don/6-november-2017-dengue-burkina-faso/en/','https://www.who.int/csr/don/2010_10_25a/en/','https://www.who.int/csr/don/2014_01_09_h5n1/en/','https://www.who.int/csr/don/2014_07_17_polio/en/','https://www.who.int/csr/don/2014_08_06_ebola/en/','https://www.who.int/csr/don/2014_07_17_ebola/en/','https://www.who.int/csr/don/05-March-2020-ebola-drc/en/','https://www.who.int/csr/don/1996_11_28c/en/','https://www.who.int/csr/don/2014_6_23polio/en/','https://www.who.int/csr/don/2014_01_09_h5n1/en/','https://www.who.int/csr/don/04-march-2020-measles-car/en/', 'https://www.who.int/csr/don/2008_12_26a/en/', 'https://www.who.int/csr/don/2013_11_26polio/en/', 'https://www.who.int/csr/don/28-september-2015-cholera/en/', 'https://www.who.int/csr/don/05-october-2018-monkeypox-nigeria/en/', 'https://www.who.int/csr/don/2010_04_30a/en/', 'https://www.who.int/csr/don/2008_01_02/en/', 'https://www.who.int/csr/don/2006_08_21/en/', 'https://www.who.int/csr/don/2003_09_30/en/', 'https://www.who.int/csr/don/2001_07_18/en/', 'https://www.who.int/csr/don/1999_12_22/en/', 'https://www.who.int/csr/don/1996_02_29b/en/', 'https://www.who.int/csr/don/19-december-2016-1-mers-saudi-arabia/en/', 'https://www.who.int/csr/don/06-october-2016-polio-nigeria/en/', 'https://www.who.int/csr/don/12-january-2020-novel-coronavirus-china/en/','https://www.who.int/csr/don/03-june-2016-oropouche-peru/en/']
    #start_urls = ['https://www.who.int/csr/don/19-March-2020-ebola-drc/en/']
    
    def parse(self, response):
        headline = response.css(".headline::text").extract()[0]
        
        publication_date = response.xpath('//meta[@name="DC.date.published"]/@content')[0].extract()
        #convert yyyy_mm_dd and dd_month_yyyy for database
  
        key_terms = [] #list of strings
        #separate related_terms, get rid of [...]
        related_terms = response.xpath('//meta[@name="DC.keywords"]/@content')[0].extract()
        related_terms = re.sub('\[.*?\]', '', related_terms)
        key_terms = related_terms.split(',')
        for i, term in enumerate(key_terms):
            key_terms[i] = term.strip()
            
        maintext = response.css('div#primary').extract()[0].split('<h3 class="section_head1"')[0].split('<!-- close of the meta div -->')
        alltext = response.css('div#primary').extract()[0]
        key_terms = key_terms_helper(alltext.lower(), key_terms)

        #convert all numbers written in words into numbers
        #join numbers like 18 038 to 18038
        alltext = re.sub('(?<=\d) (?=\d)', '', alltext)
        alltext = re.sub('(?<=\d),(?=\d)', '', alltext)
        cases = find_cases(response, text2digits.Text2Digits().convert(alltext))
        deaths = find_deaths(response,text2digits.Text2Digits().convert(alltext))
        controls = find_all_controls(response)

        maintext = format_maintext(maintext,response)
        
        # WHO already separated reports per article mostly 
        # creates reports based on diseases found in title and separates them if more than one is found
        
        # finds event dates
        paragraph = maintext.split('\n')
        event_dates = event_date_helper(get_first_paragraph(response.url))
        # puts event dates into proper format
        time = get_time_and_zone(response.url)
        event_date = event_date_range(event_dates,response,headline,time)
        
        # finds diseases mentioned in the title
        disease_temp = response.css(".headline::text").extract()[0]
        disease_temp = re.sub(' [^0-9A-Za-z] | in |,', '!', disease_temp)
        report_disease = disease_temp.split('!')[0]
        if (re.search("^[0-9 ]+$", report_disease)):
            report_disease = disease_temp.split('!')[1]
        if (re.search(" and ",report_disease)):
            if (re.search("hand",report_disease) and re.search("foot",report_disease) and re.search("mouth",report_disease)):
                report_disease = re.sub("foot and",'foot !', report_disease)
            report_disease = report_disease.split(" and ")
            for d in report_disease:
                d = re.sub('!', 'and', d)
        else:
            report_disease = [report_disease]
        # gets proper disease names 
        diseases = get_disease_name(report_disease,maintext)
        # finds extra disease reports in the maintext
        extra_report_diseases = find_more_diseases(maintext, diseases)
        # gets proper disease names
        extra_diseases = get_disease_name(extra_report_diseases, maintext)
        all_diseases = report_disease + extra_report_diseases

        # MAKING DISEASE REPORTS
        # need to add locations, country, cases, deaths by reports

        # adds basic news reports to list
        reports = []
        for d1,d2 in zip(diseases, report_disease):
            control_list = get_control_list(all_diseases,controls,d2)
            if (len(diseases) == 1):
                symptom = get_symptoms(response)
                if (symptom is None):
                    symptom = syndrome_helper(response)
                sources = get_sources(response,0,d2)
                cases = find_cases(response, text2digits.Text2Digits().convert(alltext))
                locations = find_locations(alltext)
                deaths = find_deaths(response,text2digits.Text2Digits().convert(alltext))
            else:
                symptom = find_symptoms(response,all_diseases,d2)
                sources = get_sources(response,1,d2)
                cases = get_mult_cases(response, d2, text2digits.Text2Digits().convert(alltext))
                deaths = get_mult_deaths(response, d2, text2digits.Text2Digits().convert(alltext))
                locations = find_mult_locations(alltext, d2)
            proper_symptoms = get_syndrome_name(symptom)
            #r_dict = {
            #    'event-date': event_date,
           #     'disease': d1,
            #    'controls': format_controls_sources(control_list),
             #   'syndromes': proper_symptoms,
              #  'source': format_controls_sources(sources)
            #}

            r_dict = ReportsItem()
            r_dict['event_date'] = event_date
            r_dict['disease'] = d1
            r_dict['controls'] = format_controls_sources(control_list)
            r_dict['syndromes'] = proper_symptoms
            r_dict['source'] = format_controls_sources(sources)
            r_dict['cases'] = cases
            r_dict['deaths'] = deaths
            r_dict['key_terms'] = key_terms
            r_dict['locations'] = locations
            r_dict['timezone'] = get_zone(time)
            reports.append(r_dict)
            
        
        # gets dates related to the extra diseases by using the paragraph it was found in
        dates = []
        p_found = -1
        for d in extra_report_diseases:
            i = 0
            for p in paragraph:
                if (re.search(d, p, re.IGNORECASE)):
                    date = event_date_helper(paragraph[i])
                    # puts dates into proper formats
                    date = event_date_range(date,response,headline,None)
                    dates.append(date)
                    break
                i += 1

        # makes new disease reports for extra diseases found and adds to list
        for d1, e, d2 in zip(extra_diseases, dates, extra_report_diseases):
            control_list = get_control_list(all_diseases,controls,d2)
            symptom = find_symptoms(response,all_diseases,d2)
            proper_symptoms = get_syndrome_name(symptom)
            sources = get_sources(response,1,d2)
            #r_dict = {
            #    'event-date': e,
            #    'disease': d1,
           #     'controls': format_controls_sources(control_list),
           #     'syndromes': proper_symptoms,
           #     'source': format_controls_sources(sources),
           # }
            r_dict = ReportsItem()
            r_dict['event_date'] = e
            r_dict['disease'] = d1
            r_dict['controls'] = format_controls_sources(control_list)
            r_dict['syndromes'] = proper_symptoms
            r_dict['source'] = format_controls_sources(sources)
            r_dict['cases'] = None
            r_dict['deaths'] = None
            r_dict['key_terms'] = key_terms
            r_dict['locations'] = locations
            r_dict['timezone'] = get_zone(time)
            reports.append(r_dict)

        #scraped_info = {
        #    'url': response.url,
        #    'headline': headline,
        #    'publication-date': publication_date,
        #    'maintext': get_first_paragraph(response.url),
        #    'reports': reports,
        #    'key_terms': key_terms,
        #    'cases': cases,
        #    'deaths': deaths
        #}
        scraped_info = WhoScraperItem()
        scraped_info['url'] = response.url
        scraped_info['headline'] = headline
        scraped_info['publication_date'] = publication_date
        scraped_info['maintext'] = get_first_paragraph(response.url)
        scraped_info['reports'] = reports

        # YIELD INSERTS DATA INTO DATABASES
        yield scraped_info

disease_dict = [
    { "name": "anthrax cutaneous" },
    { "name": "anthrax gastrointestinous" },
    { "name": "anthrax inhalation" },
    { "name": "botulism" },
    { "name": "brucellosis" },
    { "name": "chikungunya" },
    { "name": "cholera" },
    { "name": "cryptococcosis" },
    { "name": "cryptosporidiosis" },
    { "name": "crimean-congo haemorrhagic fever" },
    { "name": "dengue" },
    { "name": "diphteria" },
    { "name": "ebola haemorrhagic fever" },
    { "name": "ehec (e.coli)" },
    { "name": "enterovirus 71 infection" },
    { "name": "influenza a/h5n1" },
    { "name": "influenza a/h7n9" },
    { "name": "influenza a/h9n2" },
    { "name": "influenza a/h1n1" },
    { "name": "influenza a/h1n2" },
    { "name": "influenza a/h3n5" },
    { "name": "influenza a/h3n2" },
    { "name": "influenza a/h2n2" },
    { "name": "hand, foot and mouth disease" },
    { "name": "hantavirus" },
    { "name": "hepatitis a" },
    { "name": "hepatitis b" },
    { "name": "hepatitis c" },
    { "name": "hepatitis d" },
    { "name": "hepatitis e" },
    { "name": "histoplasmosis" },
    { "name": "hiv/aids" },
    { "name": "lassa fever" },
    { "name": "malaria" },
    { "name": "marburg virus disease" },
    { "name": "measles" },
    { "name": "mers-cov" },
    { "name": "mumps" },
    { "name": "nipah virus" },
    { "name": "norovirus infection" },
    { "name": "pertussis" },
    { "name": "plague" },
    { "name": "pneumococcus pneumonia" },
    { "name": "poliomyelitis" },
    { "name": "q fever" },
    { "name": "rabies" },
    { "name": "rift valley fever" },
    { "name": "rotavirus infection" },
    { "name": "rubella" },
    { "name": "salmonellosis" },
    { "name": "sars" },
    { "name": "shigellosis" },
    { "name": "smallpox" },
    { "name": "staphylococcal enterotoxin b" },
    { "name": "thypoid fever" },
    { "name": "tuberculosis" },
    { "name": "tularemia" },
    { "name": "vaccinia and cowpox" },
    { "name": "varicella" },
    { "name": "west nile virus" },
    { "name": "yellow fever" },
    { "name": "yersiniosis" },
    { "name": "zika" },
    { "name": "legionares" },
    { "name": "listeriosis" },
    { "name": "monkeypox" },
    { "name": "COVID-19" }
]   

def remove_accents(input_str):
    nfkd_form = unicodedata.normalize('NFKD', input_str)
    return u"".join([c for c in nfkd_form if not unicodedata.combining(c)])

def find_locations(text):
    locations = []
    found_state = "no"
    for country in pycountry.countries:
        if country.name in text: #found a country
            #print(country)
            #get ISO code and find all states/cities in country
            #pycountry's subdivision isn't specific enough
            subdiv = GeoText(text, country.alpha_2).cities
            #for every city mentioned save {"country": "location"}
            #if sub1 is empty save location as empty string
            # TO DO: IDK SOMEHOW GET STATES AND PROVINCE MENTIONS TOO even if it matches slightly? need a way to string match
            for cities in subdiv:
                location = create_location(country.name, cities)
            foundState = "no"
            for sub in pycountry.subdivisions.get(country_code = country.alpha_2):
                if remove_accents(sub.name) in text or sub.name in text:
                    location = create_location(country.name, sub.name)
                    found_state = "yes"
            #if there's no more specific info given
            if not subdiv and found_state == "no":
                location = create_location(country.name, "")
            if (seen_location(locations,location) == False):
                locations.append(location)
    return locations

#only grab sentences with disease
def find_mult_locations(text, d2):
    locations = []
    text = re.sub(r'<h1.*?>.*?h1>','',text)
    text_list = list(map(str.strip, re.split(r"[.!?](?!$)", text)))
    for texts in text_list:
        if d2.lower() in texts.lower():
            loc1 = find_locations(texts)
            for location in loc1:
                if seen_location(locations, location) is False:
                    locations.append(location)
    return locations

def create_location(country, location):
    loc = LocationsItem()
    loc['country'] = country
    loc['location'] = location
    return loc

def seen_location(locations, location):
    seen = False
    for loc in locations:
        if loc['country'] == location['country'] and loc['location'] == location['location']:
            seen = True
    return seen

def format_maintext(maintext,response):
    if len(maintext) == 1: 
        maintext = maintext[0]
        section_check = re.search('<h5 class="section_head3">', maintext)
        if (section_check):
            maintext = maintext.split('<h5 class="section_head3">')[0]
        section_check = re.search('<ul class="list">', maintext)
        if (section_check):
            maintext = maintext.split('<ul class="list">')[0]
        if (len(response.css('.dateline').extract()) > 0):
            maintext = re.sub('^ ', '', re.sub(' +', ' ', re.sub(r'<[^>]*?>', '', '\n'.join(''.join(maintext.replace('\n', ' ').replace('<span>','\n').split('</span>')[0:]).replace('\t','').split('\n')[1:]))))
        else: 
            maintext = re.sub('^ ', '', re.sub(' +', ' ', re.sub(r'<[^>]*?>', '', '\n'.join(''.join(maintext.replace('\n', ' ').replace('<span>','\n').split('</span>')[1:]).replace('\t','').split('\n')[1:]))))
    else:
        maintext = maintext[1]
        section_check = re.search('<h5 class="section_head3">', maintext)
        if (section_check):
            maintext = maintext.split('<h5 class="section_head3">')[0]
        section_check = re.search('<ul class="list">', maintext)
        if (section_check):
            maintext = maintext.split('<ul class="list">')[0]
        maintext = re.sub(r'<[^>]*?>', '', "\n".join(maintext.split('<span>')[1:])).replace('\n\t\t\n  \t\t\n  \t\t\n', '\n').rstrip()
        if maintext is '': 
            maintext = response.css('div#primary').extract()[0].split('<h3 class="section_head1"')[1]
            maintext = re.sub(r'<[^>]*?>', '', "\n".join(maintext.split('<span>')[1:])).replace('\n\t\t\n  \t\t\n  \t\t\n', '\n').rstrip()
    maintext = maintext.replace('\n','')
    maintext = maintext.replace('\r','')
    maintext = re.sub(r'\.(?=\S)','. ', maintext)
    maintext = maintext.replace('  ',' ')
    return maintext

def event_date_helper(text):
    event_date_list = []
    date_found = re.search(r'([0-9]{1,2}((-)|( (to|and) )))?([0-9]{1,2}((th|rd|st) of)? )?(January|February|March|April|May|June|July|August|September|October|November|December)( (and|to) (January|February|March|April|May|June|July|August|September|October|November|December))?( [0-9]{4})?', text)
    if (date_found):
        date_found = date_found.group()
        event_date_list.append(date_found)
        while(date_found is not None):
            text = text.replace(date_found, '')
            date_found = re.search(r'([0-9]{1,2}((-)|( (to|and) )))?([0-9]{1,2}((th|rd|st) of)? )?(January|February|March|April|May|June|July|August|September|October|November|December)( (and|to) (January|February|March|April|May|June|July|August|September|October|November|December))?( [0-9]{4})?', text)
            if (date_found):
                date_found = date_found.group()
                event_date_list.append(date_found)
            else:
                date_found = None
    return event_date_list

def diseases_helper(text):
    disease_list = []
    diseases = 'congo haemorrhagic fever|congo fever|ebola|dengue|diphteria|ebola haemorrhagic fever|ehec|ecoli|enterovirus 71 infection|enterovirus|influenza|influenza a/h5n1|influenza a/h7n9|influenza a/h9n2|influenza a/h1n1|influenza a/h1n2|influenza a/h3n5|influenza a/h3n2|influenza a/h2n2|influenza a(h5n1)|influenza a(h7n9)|influenza a(h9n2)|influenza a(h1n1)|influenza a(h1n2)|influenza a(h3n5)|influenza a(h3n2)|influenza a(h2n2)|hand, foot and mouth disease|hantavirus|hepatitis|hepatitis a|hepatitis b|hepatitis c|hepatitis d|hepatitis e|histoplasmosis|hiv|aids|lassa fever|lassa|malaria|marburg virus disease|marbug|measles|mers-cov|mers|mumps|nipah virus|nipah|norovirus infection|norovirus|pertussis|plague|pneumococcus pneumonia|pneumococcus|legionellosis|pneumonia|polio|q fever|rabies|rift valley fever|rift valley|rotavirus infection|rotavirus|rubella|salmonellosis|salmonella|sars|shigellosis|smallpox|staphylococcal enterotoxin b|staphylococcal|enterotoxin|thypoid fever|thypoid|tuberculosis|tularemia|vaccinia|cowpox|varicella|west nile virus|west nile|yellow fever|yersiniosis|zika|legionares|listeriosis|monkeypox|2019nCoV|coronavirus|pox|zika|legionnaire|virus|anthrax|botulism|smallpox|tularemia|junin|machupo|guanarito|chapare|lujo|cholera|meningitis'
    disease_found = re.search(diseases, text)
    if (disease_found):
        disease_found = disease_found.group()
        disease_list.append(disease_found)
        while(disease_found is not None):
            text = text.replace(disease_found, '')
            disease_found = re.search(diseases, text)
            if (disease_found):
                disease_found = disease_found.group()
                disease_list.append(disease_found)
            else:
                disease_found = None
    return disease_list

def get_symptoms(response):
    text = ''.join(response.css('div#primary p span::text').extract()) 
    text = text.split('.')
    symptoms = []
    for t in text:
        symptom_found = re.search('symptom',t,re.IGNORECASE)
        if (symptom_found):
            re.sub('/\[a-n]','',t)
            symptoms.append(t)
    return symptoms
            
def find_symptoms(response,all_diseases, curr_disease):
    paragraph = response.css('div#primary p span::text').extract()
    all_diseases.remove(curr_disease)
    other_diseases = '|'.join(all_diseases)
    symptoms = []
    for p in paragraph:
        disease_found = re.search(curr_disease,p,re.IGNORECASE)
        if (disease_found):
            line = p.split('.')
            symptom_para = re.search('symptom',p,re.IGNORECASE)
            if (symptom_para and re.search(other_diseases, p,re.IGNORECASE)):
                for l in line:
                    symptom_found = re.search('symptom',l,re.IGNORECASE)
                    disease_found = re.search(curr_disease,l,re.IGNORECASE)
                    if (symptom_found and disease_found):
                        re.sub('/\[a-n]','',l)
                        symptoms.append(l)
            elif(symptom_para and not re.search(other_diseases, p,re.IGNORECASE)):
                for l in line:
                    symptom_found = re.search('symptom',l,re.IGNORECASE)
                    if (symptom_found):
                        re.sub('/\[a-n]','',l)
                        symptoms.append(l)
    return symptoms

def syndrome_helper(response):
    text = ''.join(response.css('div#primary p span::text').extract()) 
    syndrome_list = []
    symptoms = 'haemorrhagic|feverish|paralysis|gastro|respiratory|influenza-like|rash|encephalitis|meningitis|diarrhea|diarrhoea|itch|red skin|headache|seizure|nausea|vomiting|runny nose|muscle pain|muscle ache|congestion|rhinorrhea|sneezing|sore throat|scratchy throat|cough|odynophagia|painful swallowing|drowsiness|coma|paralytic|stomach cramp'
    symptom_found = re.search(symptoms, text)
    if (symptom_found):
        symptom_found = symptom_found.group()
        syndrome_list.append(symptom_found)
        while(symptom_found is not None):
            text = text.replace(symptom_found, '')
            symptom_found = re.search(symptoms, text)
            if (symptom_found):
                symptom_found = symptom_found.group()
                syndrome_list.append(symptom_found)
            else:
                symptom_found = None
    return syndrome_list

def get_syndrome_name(syndromes):
    new_syndromes = []
    fever_check = 0
    for i in syndromes:
        if 'acute' in i.lower():
                fever_type = re.findall('respiratory|paral|gastro|fever|rash',i,re.IGNORECASE)
                if (fever_type):
                    fever_type = ' '.join(fever_type)
                    if 'respiratory' in fever_type.lower():
                        new_syndromes.append("Acute respiratory syndrome")
                    if 'paral' in fever_type.lower():
                        new_syndromes.append("Acute Flacid Paralysis")
                    if 'gastro' in fever_type.lower():
                        new_syndromes.append("Acute gastroenteritis")
                    if 'fever' in fever_type.lower() and 'rash' in fever_type.lower():
                        new_syndromes.append("Acute fever and rash")
        elif 'respiratory' in i.lower() or 'pneumonia' in i.lower() or 'lung' in i.lower():
            new_syndromes.append("Acute respiratory syndrome")
        elif 'influenza-like' in i.lower() or re.search('flu|cough|runny nose|congestion|rhinorrhea|sneez|thraot|shiver',i,re.IGNORECASE):
            new_syndromes.append("Influenza-like illness")
            fever_check = 1
        elif re.search('meningitis|nausea|cold (hand|feet)|bulging',i,re.IGNORECASE) or 'fever' in i.lower() and 'headache' in i.lower() and 'neck' in i.lower():
            new_syndromes.append("Meningitis")
            fever_check = 1
        elif ('fever' in i.lower() and 'headache' in i.lower()) or re.search('encephalitis|drows(y|iness)|confusion|seizure|halluc|coma|irritab',i,re.IGNORECASE):
            new_syndromes.append("Encephalitis")
            fever_check = 1
        elif re.search('gastro|diarrhea|diarrhoea|abdominal|cramps|stomach|vomit',i,re.IGNORECASE):
            new_syndromes.append("Acute gastroenteritis")
            fever_check = 1
        elif re.search('paral|eye|weakness|swallowing|slurred|muscle',i,re.IGNORECASE):
            new_syndromes.append("Acute Flacid Paralysis")
        if 'fever' in i.lower():
            fever_type = re.findall('rash|haemorrhagic',i,re.IGNORECASE)
            if (fever_type):
                fever_type = ' '.join(fever_type)
                if 'rash' in fever_type.lower():
                    new_syndromes.append("Acute fever and rash")
                if 'haemorrhagic' in fever_type.lower():
                    new_syndromes.append("Haemorrhagic Fever")
        if 'rash' in i.lower():
            if ('Meningitis' not in new_syndromes and 'Acute fever and rash' not in new_syndromes):
                new_syndromes.append('Meningitis')
                fever_check = 1
        if 'fever' in i.lower():
            if (fever_check == 0 and 'Haemorrhagic Fever' not in new_syndromes and 'Acute fever and rash' not in new_syndromes):
                    new_syndromes.append("Fever of Unknown Origin")
    new_syndromes = list( dict.fromkeys(new_syndromes) )
    if fever_check == 1 and 'Fever of Unknown Origin' in new_syndromes:
        new_syndromes.remove('Fever of Unknown Origin')
    return new_syndromes

def find_influenza_type(maintext, text):
    types = ['h5n1','h7n9','h9n2','h1n1','h1n2','h3n5','h3n2','h2n2']
    for t in types:
        check = re.search(t, maintext, re.IGNORECASE)
        if (check):
            return 'influenza a/' + t

def get_disease_name(disease,maintext):
    new_diseases = []
    for f in disease:
        influenza = 0
        check = 0
        proper_diseases = []
        for d in disease_dict:
            words = f.split( )
            for w in words:
                w = w.replace('(','')
                w = w.replace(')','')
                w = w.replace(']','')
                w = w.replace('[','')
                w = w.replace('{','')
                w = w.replace('}','')
                if (re.search(w, 'fever|virus|infection|disease', re.IGNORECASE)):
                    continue
                if (re.search(w, d["name"],re.IGNORECASE)):
                    if (re.search(w,'influenza',re.IGNORECASE)):
                        influenza = 1
                    proper_diseases.append(d["name"])
                    check = 1
        if (check == 0):
            if (re.search('polio',f,re.IGNORECASE)):
                proper_diseases.append("poliomyelitis")
            if (re.search('corona',f,re.IGNORECASE)):
                proper_diseases.append('COVID-19')
            if (re.search('Legionellosis',f,re.IGNORECASE)):
                proper_diseases.append('legionares')
        if (len(proper_diseases) > 0):
            disease_count = Counter(proper_diseases)
            dis, count = disease_count.most_common(1)[0]
            if (influenza == 1 and count == 0):
                new_diseases.append(find_influenza_type(maintext, f))
            else:
                new_diseases.append(dis)
    new_diseases = list( dict.fromkeys(new_diseases))
    if (len(disease) != 0 and len(new_diseases) == 0):
        new_diseases = ['other']
    if (len(new_diseases) == 0):
        new_diseases = ['unknown']
    return new_diseases

def key_terms_helper(text, terms_list):
    terms = 'outbreak|infection|fever|virus|epidemic|infectious|illness|bacteria|emerging|unknown virus|mystery disease|mysterious disease|zika|mers|salmonella|legionnaire|measles|category a agents|anthrax|botulism|plague|smallpox|pox|tularemia|junin fever|machupo fever|guanarito fever|chapare fever|lassa fever|lujo fever|hantavirus|rift valley fever|crimean congo hemorrhagic fever|dengue|ebola|marburg'
    terms_found = re.search(terms, text)
    if (terms_found):
        terms_found = terms_found.group()
        terms_list.append(terms_found)
        while(terms_found is not None):
            text = text.replace(terms_found, '')
            terms_found = re.search(terms, text)
            if (terms_found):
                terms_found = terms_found.group()
                terms_list.append(terms_found)
            else:
                terms_found = None
    return terms_list

def event_date_range(event_dates,response,headline,time):
    new_dates = []
    temp_event_dates = []
    for e in event_dates:
        if (re.search('and ',e,re.IGNORECASE)):
            date_2 = e.split('and ')[1]
            date_1 = e.split('and ')[0] + ' '.join(date_2.split(' ')[1:])
            temp_event_dates.append(date_1)
            temp_event_dates.append(date_2)
        else:
            temp_event_dates.append(e)
    new_dates = convert_dates(temp_event_dates, ' ', headline, response)
    if (len(new_dates) == 0):
        event_date = re.findall('\d{4}_\d{2}_\d{2}', response.url)
        if len(event_date) == 0:
            event_date = response.url.split('don/')[1].split('-')[:3]
            if (len(event_date) < 2):
                dateline = response.css('div#primary p .dateline::text').extract()
                if (dateline):
                    month = convert_month(dateline[0].split(' ')[1])
                    if (len(dateline[0].split(' ')[0]) == 1):
                        day = '0' + dateline[0].split(' ')[0]
                    else:
                        day = dateline[0].split(' ')[0]
                    year = dateline[0].split(' ')[2]
                    event_date = year + '-' + month + '-' + day + ' xx:xx:xx'
                else:
                    event_date = 'xxxx-xx-xx xx:xx:xx'
            else:
                month = convert_month(event_date[1])
                event_date = event_date[2]+'-'+month+'-'+event_date[0]+' xx:xx:xx'
        else:
            event_date = re.sub(r'_','-',event_date[0])+' xx:xx:xx'
    else:
        new_dates.sort()
        first_date = new_dates[0]
        # checks if there's a date that mentions the day
        temp_first = str(first_date)
        if (temp_first[-2:] == '00'):
            for n in new_dates:
                curr = str(n)
                if curr[-2:] != '00' and temp_first[:-2] == curr[:-2]:
                    first_date = n
                    break
        last_date = new_dates[len(new_dates)-1]
        if (first_date != last_date):
            date1 = format_date(first_date, time)
            date2 = format_date(last_date, 'xx:xx:xx')
            event_date = date1 + ' to ' + date2
        else:
            event_date = format_date(first_date, time)
    return event_date

def format_date(date, time):
    date = str(date)
    year = date[:4]
    if (year == '0000'):
        year = 'xxxx'
    month = date[4:6]
    if (month == '00'):
        month = 'xx'
    day = date[6:]
    if (day == '00'):
        day = 'xx'
    time = get_event_time(time)
    return year + '-' + month + '-' + day + ' ' + time

def convert_month(string):
    months = [
        {'January': '01'},
        {'February': '02'},
        {'March': '03'},
        {'April': '04'},
        {'May': '05'},
        {'June': '06'},
        {'July': '07'},
        {'August': '08'},
        {'September': '09'},
        {'October': '10'},
        {'November': '11'},
        {'December': '12'},
    ]
    month = re.search('January|February|March|April|May|June|July|August|September|October|November|December',string,re.IGNORECASE)
    if (month):
        month = month.group()
        for m in months:
            mon = list(m.keys())[0]
            if (re.search(month, mon, re.IGNORECASE)):
                month = m[mon]
    return month

def convert_dates(temp_event_dates, string, headline, response):
    new_dates = []
    for e in temp_event_dates:
        day = '00'
        month = '00'
        year = '0000'
        
        dates_expanded = e.split(string)
        for d in dates_expanded:
            if (not re.search('[a-zA-Z0-9]',d)):
                continue
            date_int = re.search('[0-9]+',d,re.IGNORECASE)
            if (date_int):
                if (len(date_int.group()) > 2):
                    year = date_int.group()
                else:
                    day = date_int.group()
                    if (len(day) < 2):
                        day = '0'+day
            else:
                month = convert_month(d)
        if (year is '0000'):
            temp_year = re.search('[0-9]{4}',headline)
            if (temp_year):
                year = temp_year.group()
        if (year is '0000'):
            temp_year = re.search('[0-9]{4}', response.url)
            if (temp_year):
                year = temp_year.group()
        date = year + month + day
        date = int(date)
        new_dates.append(date)
    return new_dates

def find_cases(response, alltext):
    table = response.xpath('//*[@class="borderOn"]//tbody')
    if (table): #if there is a table outlining cases use this
        rows = table.xpath('//tr')
        row = rows[-4]
        case = row.xpath('td//text()')[-1].extract()
        case= re.sub('[^0-9]', '', case)
        if (case == ""):
            row = rows[-3]
            case = row.xpath('td//text()')[-1].extract()
            case= re.sub('[^0-9]', '', case)
        return case
    tables = response.xpath('//*[@class="tableData"]//tbody')
    if (tables): #if there is a table outlining cases use this
        rows = tables[0].xpath('//tr')
        row = rows[1]
        case = row.xpath('td//text()')[0].extract()
        case1 = row.xpath('td//text()')[1].extract()
        if (case == "Cases" or case1 == "Cases"):
            rows = tables[0].xpath('//tr')
            row = rows[-1]
            case = row.xpath('td//text()')[1].extract()
            case= re.sub('[^0-9]', '', case)
            return case
    tables = response.xpath('//div[@id="primary"]//table')
    if (tables):
        rows = tables[0].xpath('//tr')
        # errors in line below, list index out of range https://www.who.int/csr/don/2002_08_23a/en/ (a lot of errors in 2002 and below)
        row = rows[1]
        case = row.xpath('td//text()')[0].extract()
        if (len(row.xpath('td//text()')) >= 2):
            case1 = row.xpath('td//text()')[1].extract()
        # errors in line below as case1 isn't assigned sometimes
        if (case == "Cases" or case1 == "Cases"):
            rows = tables[0].xpath('//tr')
            row = rows[-1]
            case = row.xpath('td//text()')[1].extract()
            case= re.sub('[^0-9]', '', case)
            return case
    #otherwise look through all text and find 'totals' (find confirmed here too)
    case = re.search('total (of )?[ 0-9]+| (\(H1N1\) )?[ 0-9]+ confirmed case(s)?', alltext) #finds first one only automatically
    #H1n1 case is because some reports name it h1n1 2009 (reports sometimes say h1n1 2009 confirmed cases)
    if (case):
        case = case.group()
        year = re.search('\(H1N1\)', case)
        if (year):
            case = None
        else:
            case = int(''.join(filter(str.isdigit, case)))
            return case
    #otherwise look for all other ways of saying cases
    case = re.search(' (\(H1N1\) )?[0-9]+( suspected| new| laboratory-confirmed| confirmed| laboratory confirmed)? case(s)?| (\(H1N1\) )?[ 0-9]+(st|rd|nd|th) case| (\(H1N1\) )?[ 0-9]+ laboratory confirmed| (\(H1N1\) )?[ 0-9]+ patients with clinical symptoms', alltext)
    if (case):
        case = case.group()
        year = re.search('\(H1N1\)', case)
        if (year):
            case = None
        else:
            case = int(''.join(filter(str.isdigit, case)))
            return case
    return case

#in the 2 cases this happens: cases of f2
def get_mult_cases(response, d2, alltext):
    #otherwise look for all other ways of saying cases
    case = re.search('(\(H1N1\) )?[0-9]+( suspected| new| laboratory-confirmed| confirmed)? case(s)?.*? of.*?\.|\..*?(\(H1N1\) )?[ 0-9]+ patients with clinical symptoms consistent with.*?\.', alltext)
    if (case):
        case = case.group()
        year = re.search('\(H1N1\)', case)
        if (year) or d2.lower().replace('-',' ') not in case.lower():
            #remove what we found from alltext and find again
            while True:
                # line below has errors, says case is None somtimes
                alltext1 = alltext.replace(case,"")
                case = re.search('(\(H1N1\) )?[0-9]+( suspected| new| laboratory-confirmed| confirmed| laboratory confirmed)? case(s)?.*? of.*?\.|\..*?(\(H1N1\) )?[ 0-9]+ patients with clinical symptoms consistent with.*?\.', alltext1)
                if (case):
                    case = case.group()
                    if d2.lower() in case.lower():
                        case = re.search('(\(H1N1\) )?[0-9]+( suspected| new| laboratory-confirmed| confirmed| laboratory confirmed)? case(s)? of| (\(H1N1\) )?[ 0-9]+(st|rd|nd|th) case| (\(H1N1\) )?[ 0-9]+ laboratory confirmed| (\(H1N1\) )?[ 0-9]+ patients with clinical symptoms', case)
                        case = case.group()
                        case = int(''.join(filter(str.isdigit, case)))
                        return case
        else:
            case = re.search('(\(H1N1\) )?[0-9]+( suspected| new| laboratory-confirmed| confirmed|laboratory confirmed)? case(s)?| (\(H1N1\) )?[ 0-9]+(st|rd|nd|th) case| (\(H1N1\) )?[ 0-9]+ laboratory confirmed| (\(H1N1\) )?[ 0-9]+ patients with clinical symptoms', case)
            case = case.group()
            case = int(''.join(filter(str.isdigit, case)))
            return case
    return case #None

def get_mult_deaths(response, d2, alltext):
    #otherwise look for all other ways of saying cases
    deaths = re.search('(\.|>).*?[0-9]+ death(s)?.*?\.|(\.|>).*?[0-9]+ case(s)? died.*?\.|(\.|>).*?[0-9]+ of fatal.*?\.|(\.|>).*?[0-9]+ fatal.*?\.|(\.|>).*?[0-9]+ (were|was) fatal.*?\.|(\.|>).*?[ 0-9]+ related death(s)?.*?\.|(\.|>).*?[ 0-9]+ ha(ve|s) been fatal.*?\.|(\.|>).*?[ 0-9]+ of these cases have died.*?\.|(\.|>).*?[ 0-9]+ ha(ve|s) died.*?\.', alltext)
    if (deaths):
        deaths = deaths.group()
        if d2.lower().replace('-',' ') not in deaths.lower():
            #remove what we found from alltext and find again
            while True:
                alltext1 = alltext.replace(deaths,"")
                deaths = re.search('(\.|>|<).*?[0-9]+ death(s)?.*?\.|(\.|>).*?[0-9]+ case(s)? died.*?\.|(\.|>).*?[0-9]+ of fatal.*?\.|(\.|>).*?[0-9]+ fatal.*?\.|(\.|>).*?[0-9]+ (were|was) fatal.*?\.|(\.|>).*?[ 0-9]+ related death(s)?.*?\.|(\.|>).*?[ 0-9]+ ha(ve|s) been fatal.*?\.|(\.|>).*?[ 0-9]+ of these cases have died.*?\.|(\.|>).*?[ 0-9]+ ha(ve|s) died.*?\.', alltext1)
                if (deaths):
                    deaths = deaths.group()
                    if d2.lower() in deaths.lower():
                        deaths = re.search(' [0-9]+ death(s)?| [0-9]+ case(s)? died| [0-9]+ of fatal| [0-9]+ fatal| [0-9]+ (were|was) fatal| [ 0-9]+ related death(s)?| [ 0-9]+ ha(ve|s) been fatal| [ 0-9]+ of these cases have died| [ 0-9]+ ha(ve|s) died', deaths)
                        deaths = deaths.group()
                        deaths = int(''.join(filter(str.isdigit, deaths)))
                        return deaths
        else:
            deaths = re.search(' [0-9]+ death(s)?| [0-9]+ case(s)? died| [0-9]+ of fatal| [0-9]+ fatal| [0-9]+ (were|was) fatal| [ 0-9]+ related death(s)?| [ 0-9]+ ha(ve|s) been fatal| [ 0-9]+ of these cases have died| [ 0-9]+ ha(ve|s) died', deaths)
            deaths = deaths.group()
            deaths = int(''.join(filter(str.isdigit, deaths)))
            return deaths
    return deaths #None

def find_deaths(response, alltext):
    table = response.xpath('//*[@class="borderOn"]//tbody')
    if (table): #if there is a table outlining cases use this
        rows = table.xpath('//tr')
        row = rows[-2]
        if (len(row.xpath('td//text()')) >= 2):
            death = row.xpath('td//text()')[-1].extract()
            death = re.sub('[^0-9]', '', death)
        else:
            row = rows[-3]
            death = row.xpath('td//text()')[-1].extract()
            death = re.sub('[^0-9]', '', death)
        return death
    #otherwise look through all text and find 'ways of saying death'
    tables = response.xpath('//*[@class="tableData"]//tbody')
    if (tables): #if there is a table outlining cases use this
        rows = tables[0].xpath('//tr')
        row = rows[1]
        death = row.xpath('td//text()')[1].extract()
        if (death == "Deaths"):
            rows = tables[0].xpath('//tr')
            row = rows[-1]
            death = row.xpath('td//text()')[2].extract()
            death = re.sub('[^0-9]', '', death)
            return death
    tables = response.xpath('//div[@id="primary"]//table')
    if (tables):
        rows = tables[0].xpath('//tr')
        row = rows[1]
        death = row.xpath('td//text()')
        if (len(death) >= 3):
            death2 = death[2].extract()
        if (len(death) >= 4):
            death1 = death[3].extract()
            if (death2 == "Deaths" or death1 == "Deaths"):
                rows = tables[0].xpath('//tr')
                row = rows[-1]
                death = row.xpath('td//text()')[2].extract()
                death = re.sub('[^0-9]', '', death)
                return death
    death = re.search(' [0-9]+ death(s)?| [0-9]+ case(s)? died| [0-9]+ of fatal| [0-9]+ fatal| [0-9]+ (were|was) fatal| [ 0-9]+ related death(s)?| [ 0-9]+ ha(ve|s) been fatal| [ 0-9]+ of these cases have died| [ 0-9]+ ha(ve|s) died', alltext) #finds first one only automatically
    if (death):
        death = death.group()
        death = int(''.join(filter(str.isdigit, death)))
        return death
    return death #none

# find any extra diseases mentioned = new report
def find_more_diseases(maintext, disease_list):
    diseases = []
    for d in disease_dict:
        diseases.append(list(d.values())[0])
    diseases = '|'.join(diseases)
    diseases = 'polio|coronavirus|influenza|anthrax|ebola|ehec|ecoli|enterovirus|hiv|aids|lassa|marbug|mers|mipah|norovirus|pneumonia|rotavirus|thypoid|cowpox' + diseases
    diseases = '(' + diseases + ')'
    found = re.findall(diseases,maintext,re.IGNORECASE)
    found = [tuple(j for j in i if j)[-1] for i in found]
    remove = []
    for d in disease_list:
        i = 0
        for f in found:
            if (re.search(f,d,re.IGNORECASE)):
                remove.append(i)
            else:
                if (d == 'COVID-19' and re.search('coronavirus',f,re.IGNORECASE)):
                    remove.append(i)
            i += 1
    remove.sort(reverse=True)
    for i in remove:
        del found[i]
    result = []
    for f in found:
        f = f.lower()

    found = list( dict.fromkeys(found))
    for f in found:
        for m in maintext.split('.'):
            if (re.search(f,m,re.IGNORECASE)):
                if (re.search('case|outbreak',m,re.IGNORECASE)):
                    if (f not in result):
                        result.append(f)
    return result

def find_all_controls(response):
    controls = []
    text = response.css('div#primary').extract()[0].split('</h3>')
    i = 0
    check = 0
    for t in text:
        if (re.search('public health response', t, re.IGNORECASE)):
            check = 1
            break
        i += 1
    if (check is 1 and len(text) > i+1):
        text = text[i+1]
        if (re.search('<li>',text)):
            for t in text.split('<li>')[1:]:
                if (re.search('</li>',t)):
                    if (re.search(';',t)):
                        index = t.index(';')
                    else:
                        index = t.index('<')
                    control = t[:index]
                    re.sub('/\[a-n]','',control)
                    controls.append(control)
    paragraph = response.css('div#primary p span::text').extract()
    for p in paragraph:
        for l in p.split('.'):
            if (re.search('control measures|protective measures', l, re.IGNORECASE)):
                re.sub('/\[a-n]','',l)
                controls.append(l)
    return controls


def get_control_list(report_disease,controls,d2):
    control_list = []
    check_diseases = '|'.join(report_disease)
    if (len(report_disease) == 1):
        control_list = controls
    else:
        for c in controls:
            if (not re.search(check_diseases,c)):
                control_list.append(c)
            if (re.search(d2,c,re.IGNORECASE)):
                control_list.append(c)
    return control_list

def get_sources(response, many, disease):
    sources = []
    paragraph = response.css('div#primary p span::text').extract()
    for p in paragraph:
        for l in p.split('.'):
            if (re.search('(caused|transmitted|contributed)( primarily)? (by|through|to)',l)):
                re.sub('/\[a-n]','',l)
                if (many):
                    if (re.search(disease,l,re.IGNORECASE)):
                        sources.append(l)
                else:
                    sources.append(l)
    return sources

def format_controls_sources(controls_list):
    new_controls = []
    for c in controls_list:
        if ('a href' in c):
            continue
        c = c.strip()
        c = c.replace('\n',' ')
        c = c.replace('\r',' ')
        c = re.sub('(\.|,|;|:)$','',c)
        c = re.sub(r'<[^>]*?>', '', c)
        new_controls.append(c)
    controls = ' & '.join(new_controls)
    controls = re.sub(' & $','',controls)
    controls = controls.strip()
    controls = re.sub('^[^A-Za-z0-9]+', '', controls)
    return controls

def get_first_paragraph(url):
    c = urlopen(url)
    contents = c.read()
    soup = BeautifulSoup(contents,'html.parser')
    content = soup.find('div',{'id': 'primary'})
    for div in content.find_all('div',{'class':'meta'}):
        div.decompose()
    span = content.find_all('span')
    for s in span:
        if (not s.select('b') and not s.select('table')):
            if (len(s.text.split(' ')) > 10):
                printable = set(string.printable)
                first_paragraph = ''.join(filter(lambda x: x in printable, s.text))
                text = first_paragraph.replace('\n', ' ')
                text = text.replace('\r', ' ')
                text = re.sub(' +', ' ',text)
                return text.strip()
        content = soup.find('h5', {'class': 'section_head3'})
        if (s.select('table') and content):
            printable = set(string.printable)
            first_paragraph = ''.join(filter(lambda x: x in printable, content.text))
            text = first_paragraph.replace('\n', ' ')
            text = text.replace('\r', ' ')
            text = re.sub(' +', ' ',text)
            return text.strip()
    return ''

def get_time_and_zone(url):
    c = urlopen(url)
    contents = c.read()
    soup = BeautifulSoup(contents,'html.parser')
    content = soup.find('div',{'id': 'primary'})
    for div in content.find_all('div',{'class':'meta'}):
        div.decompose()
    span = content.find_all('span')
    for s in span:
        time_zone = re.search('([0-9]{4}|[0-9]{2}:[0-9]{2}) [A-Z]{3,4}',s.text)
        cases = re.search('([0-9]{4}|[0-9]{2}:[0-9]{2}) [A-Z]{3,4} case',s.text)
        if (time_zone and not cases):
            time = time_zone.group().split(' ')[0]
            zone = time_zone.group().split(' ')[1]
            if (zone in pytz.all_timezones):
                if (':' in time):
                    hour = time.split(':')[0]  
                    minute = time.split(':')[1]
                else:
                    hour = time[:2]
                    minute = time[2:4]
                if (hour and int(hour) < 24):
                    if (minute and int(minute) < 60):
                        return time_zone.group()

def get_event_time(time_zone):
    if (time_zone):
        hour = 'xx'
        minute = 'xx'
        time = time_zone.split(' ')[0]
        if (':' in time):
            hour = time.split(':')[0]  
            minute = time.split(':')[1]
        else:
            hour = time[:2]
            minute = time[2:4]
        return hour + ':' + minute + ':xx'
    return 'xx:xx:xx'

def get_zone(time_zone):
    if (time_zone):
        return time_zone.split(' ')[1]  

    
