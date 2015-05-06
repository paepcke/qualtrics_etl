import json
import urllib2
from os.path import expanduser
import os.path
import sys
import xml.etree.ElementTree as ET
from pymysql_utils1 import MySQLDB

class QualtricsExtractor(MySQLDB):

    def __init__(self):
        '''
        Initializes extractor object with credentials from .ssh directory.
        '''
        home = expanduser("~")
        userFile = home + '/.ssh/qualtrics_user'
        tokenFile = home + '/.ssh/qualtrics_token'
        dbFile = home + "/.ssh/mysql_user"
        if os.path.isfile(userFile) == False:
            sys.exit("User file not found: " + userFile)
        if os.path.isfile(tokenFile) == False:
            sys.exit("Token file not found: " + tokenFile)
        if os.path.isfile(dbFile) == False:
            sys.exit("MySQL user credentials not found: " + dbFile)

        self.apiuser = None
        self.apitoken = None
        dbuser = None
        dbpass = None

        with open(userFile, 'r') as f:
            self.apiuser = f.readline().rstrip()

        with open(tokenFile, 'r') as f:
            self.apitoken = f.readline().rstrip()

        with open(dbFile, 'r') as f:
            dbuser = f.readline().rstrip()
            dbpass = f.readline().rstrip()

        MySQLDB.__init__(self, db="EdxQualtrics", user=dbuser, passwd=dbpass)

## Database setup helper method for client

    def setupDB(self):
        '''
        Client method loads schema to local MySQL server instance.
        '''
        # self.execute("DROP TABLE IF EXISTS `choice`;")
        # self.execute("DROP TABLE IF EXISTS `question`;")
        self.execute("DROP TABLE IF EXISTS `response`;")
        self.execute("DROP TABLE IF EXISTS `response_metadata`;")
        # self.execute("DROP TABLE IF EXISTS `survey_meta`;")

        choiceTbl = (       """
                            CREATE TABLE `choice` (
                              `SurveyId` varchar(50) DEFAULT NULL,
                              `QuestionId` varchar(50) DEFAULT NULL,
                              `ChoiceId` varchar(50) DEFAULT NULL,
                              `description` varchar(3000) DEFAULT NULL
                            ) ENGINE=MyISAM DEFAULT CHARSET=utf8;
                            """ )

        questionTbl = (     """
                            CREATE TABLE `question` (
                              `SurveyID` varchar(50) DEFAULT NULL,
                              `QuestionID` varchar(5000) DEFAULT NULL,
                              `QuestionText` varchar(5000) DEFAULT NULL,
                              `QuestionDescription` varchar(5000) DEFAULT NULL,
                              `ForceResponse` varchar(50) DEFAULT NULL,
                              `QuestionType` varchar(50) DEFAULT NULL,
                              `QuestionNumber` varchar(50) DEFAULT NULL
                            ) ENGINE=MyISAM DEFAULT CHARSET=utf8;
                            """ )

        responseTbl = (     """
                            CREATE TABLE `response` (
                              `SurveyId` varchar(50) DEFAULT NULL,
                              `ResponseId` varchar(50) DEFAULT NULL,
                              `QuestionNumber` varchar(50) DEFAULT NULL,
                              `AnswerChoiceId` varchar(500) DEFAULT NULL,
                              `Description` varchar(5000) DEFAULT NULL
                            ) ENGINE=MyISAM DEFAULT CHARSET=utf8;
                            """ )

        responseMetaTbl = ( """
                            CREATE TABLE `response_metadata` (
                              `SurveyID` varchar(50) DEFAULT NULL,
                              `ResponseID` varchar(50) DEFAULT NULL,
                              `Name` varchar(1200) DEFAULT NULL,
                              `EmailAddress` varchar(50) DEFAULT NULL,
                              `IPAddress` varchar(50) DEFAULT NULL,
                              `StartDate` datetime DEFAULT NULL,
                              `EndDate` datetime DEFAULT NULL,
                              `ext_id` varchar(200) DEFAULT NULL,
                              `ConditionID` varchar(50) DEFAULT NULL,
                              `ConditionDescription` varchar(500) DEFAULT NULL,
                              `ResponseSet` varchar(500) DEFAULT NULL,
                              `ExternalDataReference` varchar(500) DEFAULT NULL,
                              `Status` varchar(50) DEFAULT NULL,
                              `Finished` varchar(50) DEFAULT NULL
                            ) ENGINE=MyISAM DEFAULT CHARSET=utf8;
                            """ )

        surveyMeta = (      """
                            CREATE TABLE `survey_meta` (
                              `SurveyId` varchar(50) DEFAULT NULL,
                              `PodioID` varchar(50) DEFAULT NULL,
                              `SurveyCreationDate` datetime DEFAULT NULL,
                              `UserFirstName` varchar(200) DEFAULT NULL,
                              `UserLastName` varchar(200) DEFAULT NULL,
                              `SurveyName` varchar(2000) DEFAULT NULL,
                              `responses` varchar(50) DEFAULT NULL
                            ) ENGINE=MyISAM DEFAULT CHARSET=utf8;
                            """ )

        # self.execute(choiceTbl)
        # self.execute(questionTbl)
        self.execute(responseTbl)
        self.execute(responseMetaTbl)
        # self.execute(surveyMeta)

## API extractor methods

    def __getSurveyMetadata(self):
        '''
        Pull survey metadata from Qualtrics. Returns JSON object.
        '''
        url = "https://stanforduniversity.qualtrics.com/WRAPI/ControlPanel/api.php?API_SELECT=ControlPanel&Version=2.4&Request=getSurveys&User=%s&Token=%s&Format=JSON&JSONPrettyPrint=1" % (self.apiuser, self.apitoken)
        print url
        data = json.loads(urllib2.urlopen(url).read())
        return data

    def __genSurveyIDs(self):
        '''
        Generator for Qualtrics survey IDs.
        '''
        data = self.__getSurveyMetadata()
        surveys = data['Result']['Surveys']
        total = len(surveys)
        print "Extracting %d surveys from Qualtrics..." % total
        index = 0
        while index < total:
            print "Processing survey %d out of %d total." % (index+1, total)
            surveyID = surveys[index]['SurveyID']
            yield surveyID
            index += 1

    def __getSurvey(self, surveyID):
        '''
        Pull survey data for given surveyID from Qualtrics. Returns XML string.
        '''
        url="https://stanforduniversity.qualtrics.com//WRAPI/ControlPanel/api.php?API_SELECT=ControlPanel&Version=2.4&Request=getSurvey&User=%s&Token=%s&SurveyID=%s" % (self.apiuser, self.apitoken, surveyID)
        data = urllib2.urlopen(url).read()
        return ET.fromstring(data)

    def __getResponses(self, surveyID):
        '''
        Pull response data for given surveyID from Qualtrics. Returns JSON object.
        '''
        url = "https://stanforduniversity.qualtrics.com/WRAPI/ControlPanel/api.php?API_SELECT=ControlPanel&Version=2.4&Request=getLegacyResponseData&User=%s&Token=%s&Format=JSON&SurveyID=%s&Labels=1" % (self.apiuser, self.apitoken, surveyID)
        raw = urllib2.urlopen(url).read()
        data = None
        if len(raw) > 10:
            data = json.loads(raw)
        return data


## Helper method for parsing data from raw Qualtrics exports

    def __getPodioID(self, surveyID):
        '''
        Given a surveyID from Qualtrics, finds embedded field 'c' and returns
        field value. For mapping surveys to course names via Podio project IDs.
        '''
        try:
            podioID = "NULL"
            survey = self.__getSurvey(surveyID)
            embeddedFields = survey.findall('./EmbeddedData/Field')
            for ef in embeddedFields:
                if ef.find('Name').text == 'c':
                    podioID = ef.find('Value').text
        except (urllib2.HTTPError, AttributeError) as e:
            # HTTPError indicates survey no longer accessible to user
            # AttributeError indicates survey not formatted as expected
            print "%s podioID getter failed with error: %s" % (surveyID, e)
        return unicode(podioID)

## Transform methods

    def __parseSurveyMetadata(self, rawMeta):
        '''
        Given survey metadata for active user, returns a dict of dicts mapping
        column names to values for each survey.
        '''
        svMeta = dict()
        for idx, sv in enumerate(rawMeta):
            keys = ['SurveyID', 'SurveyName', 'SurveyCreationDate', 'UserFirstName', 'UserLastName', 'responses']
            data = dict()
            for key in keys:
                try:
                    val = sv[key].replace('"', '')
                    data[key] = val
                except KeyError as k:
                    data[k[0]] = 'NULL' # Set value to NULL if no data found
            data['PodioID'] = self.__getPodioID(sv['SurveyID'])
            svMeta[idx] = data # Finally, add row to master dict
        return svMeta

    def __parseSurvey(self, svID):
        '''
        Given surveyID, parses survey from Qualtrics and returns:
         1. a dict mapping db column names to values corresponding to survey questions
         2. a dict of dicts mapping db column names to choices for each question
        Method expects an XML ElementTree object corresponding to a single survey.
        '''
        # Get survey from surveyID
        sv=None
        try:
            sv = self.__getSurvey(svID)
        except urllib2.HTTPError:
            print "Survey %s not found." % svID
            return None, None

        masterQ = dict()
        masterC = dict()

        # Parse data for each question
        questions = sv.findall('./Questions/Question')
        for idx, q in enumerate(questions):
            parsedQ = dict()
            qID = q.attrib['QuestionID']
            qkeys = ['QuestionText', 'QuestionDescription']
            parsedQ['SurveyID'] = svID
            parsedQ['QuestionID'] = qID
            parsedQ['QuestionNumber'] = q.find('ExportTag').text
            parsedQ['QuestionType'] = q.find('Type').text
            try:
                parsedQ['ForceResponse'] = q.find('Validation/ForceResponse').text
            except:
                parsedQ['ForceResponse'] = 'NULL'

            for key in qkeys:
                try:
                    text = q.find(key).text.replace('"', '')
                    if len(text) > 2000:
                        text = text[0:2000]
                    parsedQ[key] = text
                except:
                    parsedQ[key] = 'NULL'

            masterQ[idx] = parsedQ

            # For each question, load all choices
            choices = q.findall('Choices/Choice')
            for c in choices:
                parsedC = dict()
                cID = c.attrib['ID']
                parsedC['SurveyID'] = svID
                parsedC['QuestionID'] = qID
                parsedC['ChoiceID'] = cID
                cdesc = c.find('Description').text
                parsedC['Description'] = cdesc.replace("'", "").replace('"', '') if (cdesc is not None) else 'N/A'
                masterC[qID+cID] = parsedC

        return masterQ, masterC

    def __parseResponses(self, svID):
        '''
        Given a survey ID, parses responses from Qualtrics and returns:
        1. A dict mapping responseIDs to any available metadata
        2. A dict of dicts containing responses per user per question
        Method expects a JSON formatted object.
        '''
        # Get responses from Qualtrics
        rsRaw = None
        try:
            rsRaw = self.__getResponses(svID)
        except urllib2.HTTPError:
            print "  Survey %s not found." % svID
            return None, None

        # Get total expected responses
        rq = 'SELECT `responses` FROM survey_meta WHERE SurveyID = "%s"' % svID
        rnum = self.query(rq).next()

        # Return if API gave us no data
        if rsRaw == None:
            print "  Survey %s not found; expected %s responses." % (svID, rnum[0])
            return None, None

        # Return if no responses
        print "Parsing %s responses from survey %s..." % (rnum[0], svID)
        if rnum[0] == 'NULL':
            return None, None

        responses = dict()
        respMeta = dict()

        for rID in rsRaw.keys():
            response = rsRaw[rID]

            # Get response metadata for each response
            # Method destructively reads question fields
            rm = dict()
            rm['SurveyID'] = svID
            rm['ResponseID'] = rID
            rm['Name'] = response.pop('Name') if 'Name' in response else 'NULL'
            rm['EmailAddress'] = response.pop('EmailAddress') if 'EmailAddress' in response else 'NULL'
            rm['IPAddress'] = response.pop('IPAddress') if 'IPAddress' in response else 'NULL'
            rm['StartDate'] = response.pop('StartDate') if 'StartDate' in response else 'NULL'
            rm['EndDate'] = response.pop('EndDate') if 'EndDate' in response else 'NULL'
            rm['ext_id'] = response.pop('a') if 'a' in response else 'NULL'
            rm['ConditionID'] = response.pop('idcond') if 'idcond' in response else 'NULL'
            rm['ConditionDescription'] = response.pop('condition') if 'condition' in response else 'NULL'
            rm['ResponseSet'] = response.pop('ResponseSet') if 'ResponseSet' in response else 'NULL'
            rm['ExternalDataReference'] = response.pop('ExternalDataReference') if 'ExternalDataReference' in response else 'NULL'
            rm['Status'] = response.pop('Status') if 'Status' in response else 'NULL'
            rm['Finished'] = response.pop('Finished') if 'Finished' in response else 'NULL'
            respMeta[rID] = rm

            # Parse remaining fields as question answers
            for q in response.keys():
                rs = dict()
                if q and '_' in q:
                    qSplit = q.split('_')
                    qNum = qSplit[0]
                    cID = qSplit[1]
                else:
                    qNum = q
                    cID = 'NULL'
                rs['SurveyID'] = svID
                rs['ResponseID'] = rID
                rs['QuestionNumber'] = qNum
                rs['AnswerChoiceID'] = cID
                desc = repr(response[q]).replace('"', '').replace("'", "").replace('\\', '').lstrip('u')
                if len(desc) >= 5000:
                    desc = desc[:5000] #trim past max db varchar length
                rs['Description'] = desc
                index = rID + "_" + q
                responses[index] = rs

        return responses, respMeta

## Convenience methods to write data to outfile.

    def __writeXML(self, data, filename):
        '''
        Convenience function for writing out XML data to file.
        '''
        filename = "xml/%s.xml" % filename
        doc = open(filename, 'w')
        doc.write(data)
        doc.close()

    def __writeJSON(self, data, filename):
        '''
        Convenience function for writing out JSON data to file.
        '''
        jstr = json.dumps(obj=data, indent=4)
        filename = "xml/%s.json" % filename
        doc = open(filename, 'w')
        doc.write(jstr)
        doc.close()


## Convenience method for handling query calls to MySQL DB.

    def __loadDB(self, data, tableName):
        '''
        Convenience function for writing data to named table. Expects data to be
        represented as a list of dicts mapping column names to values.
        '''
        for row in data:
            try:
                cols = ", ".join('%s' % key for key in row.keys())
                vals = ", ".join('"%s"' % value for value in row.values())
                query = "INSERT INTO %s(%s) VALUES (%s)" % (tableName, cols, vals)
                self.execute(query.encode('UTF-8', 'ignore'))
            except:
                print "  Query failed: %s" % query


## Client file IO methods for raw data from Qualtrics API calls.

    def writeSurveyMetadata(self):
        '''
        Client method outputs survey metadata to JSON file.
        '''
        svMeta = self.__getSurveyMetadata()
        self.__writeJSON(svMeta, "SV_meta")

    def writeSurvey(self, svID=None):
        '''
        Client method outputs one survey to XML file.
        '''
        if svID is None:
            svID = self.__genSurveyIDs().next() # use first survey by default
        sv = self.__getSurvey(svID)
        self.__writeXML(sv, svID)

    def writeAllSurveys(self):
        '''
        Client method outputs all available surveys to XML files.
        '''
        svIDs = self.__genSurveyIDs()
        for svID in svIDs:
            sv = self.__getSurvey(svID)
            self.__writeXML(sv, svID)

    def writeSurveyResponses(self, svID=None):
        '''
        Client method outputs responses for one survey to JSON file.
        '''
        if svID is None:
            svID = self.__genSurveyIDs().next() # use first survey by default
        resp = self.__getResponses(svID)
        fn = svID + "_responses"
        self.__writeJSON(resp, fn)


## Client data load methods

    def loadSurveyMetadata(self):
        '''
        Client method extracts and transforms survey metadata and loads to MySQL
        database using query interface inherited from MySQLDB class.
        '''
        rawMeta = self.__getSurveyMetadata()
        svMeta = rawMeta['Result']['Surveys']
        parsedSM = self.__parseSurveyMetadata(svMeta)
        self.__loadDB(parsedSM.values(), 'survey_meta')

    def loadSurveyData(self):
        '''
        Client method extracts and transforms survey questions and question
        choices and loads to MySQL database using MySQLDB class methods.
        '''
        sids = self.__genSurveyIDs()
        for svID in sids:
            questions, choices = self.__parseSurvey(svID)
            if (questions == None) or (choices == None):
                continue
            self.__loadDB(questions.values(), 'question')
            self.__loadDB(choices.values(), 'choice')

    def loadResponseData(self, startAfter=0):
        '''
        Client method extracts and transforms response data and response metadata
        and loads to MySQL database using MySQLDB class methods. User can specify
        where to start in the list of surveyIDs.
        '''
        sids = self.__genSurveyIDs()
        for idx, svID in enumerate(sids):
            if idx < startAfter:
                print "  Skipped surveyID %s" % svID
                continue # skip first n surveys
            responses, respMeta = self.__parseResponses(svID)
            if (responses == None) or (respMeta == None):
                continue
            self.__loadDB(responses.values(), 'response')
            self.__loadDB(respMeta.values(), 'response_metadata')



if __name__ == '__main__':

    # Setup MySQL database and extractor class
    qe = QualtricsExtractor()
    qe.setupDB()

    # Load survey data from Qualtrics
    # See profiles/ for timing information
    # qe.loadSurveyMetadata() # takes ~2m50s
    # qe.loadSurveyData() # takes ~3m40s
    qe.loadResponseData(startAfter=0) #takes ~2h TODO: Debug, profile
