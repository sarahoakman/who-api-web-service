class LogFile:

    def make_log_entry(self, accessed_time, start_time, end_time, method, url, request_body, response_body, code, db_accessed, db_updated):
        logfile = open('Logfile/logfile.txt', 'a')
        logfile.write('API Accessed Timestamp: ' + accessed_time + '\n')
        logfile.write('Elapsed Time: ' + str(end_time - start_time) + '\n')
        logfile.write('Request Method: ' + '<[' + method + ']>' + '\n')
        logfile.write('Request URL: ' + url + '\n')
        logfile.write('API Endpoint: ' + '/article' + '\n')
        logfile.write('Request Body: ' + str(request_body) + '\n')
        logfile.write('Response Description: ' + response_body + '\n')
        logfile.write('Response Code: ' + code + '\n')
        logfile.write('Resource Utilisation: ' + "{'database_accessed': '" + db_accessed +  "', 'database_updated: '" + db_updated + "'}\n")
        logfile.write('\n')
        logfile.close()