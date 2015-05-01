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
        if os.path.isfile(userFile) == False:
            sys.exit("User file not found " + userFile)
        if os.path.isfile(tokenFile) == False:
            sys.exit("Token file not found " + tokenFile)

        self.apiuser = None
        self.apitoken = None

        with open(userFile, 'r') as f:
            self.apiuser = f.readline().rstrip()

        with open(tokenFile, 'r') as f:
            self.apitoken = f.readline().rstrip()

        MySQLDB.__init__(self, db="EdxQualtrics")

## Database setup helper method for client

    def setupDB(self):
        '''
        Client method loads schema to local MySQL server instance.
        '''
        self.execute("DROP TABLE IF EXISTS `choice`;")
        self.execute("DROP TABLE IF EXISTS `question`;")
        self.execute("DROP TABLE IF EXISTS `response`;")
        self.execute("DROP TABLE IF EXISTS `response_metadata`;")
        self.execute("DROP TABLE IF EXISTS `survey_meta`;")

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
                              `SurveyId` varchar(50) DEFAULT NULL,
                              `questionid` varchar(5000) DEFAULT NULL,
                              `questiontext` varchar(5000) DEFAULT NULL,
                              `questiondescription` varchar(5000) DEFAULT NULL,
                              `ForceResponse` varchar(50) DEFAULT NULL,
                              `QuestionType` varchar(50) DEFAULT NULL
                            ) ENGINE=MyISAM DEFAULT CHARSET=utf8;
                            """ )

        responseTbl = (     """
                            CREATE TABLE `response` (
                              `SurveyId` varchar(50) DEFAULT NULL,
                              `ResponseId` varchar(50) DEFAULT NULL,
                              `QuestionId` varchar(50) DEFAULT NULL,
                              `AnswerChoiceId` varchar(500) DEFAULT NULL,
                              `Description` varchar(2000) DEFAULT NULL
                            ) ENGINE=MyISAM DEFAULT CHARSET=utf8;
                            """ )

        responseMetaTbl = ( """
                            CREATE TABLE `response_metadata` (
                              `SurveyId` varchar(50) DEFAULT NULL,
                              `name` varchar(1200) DEFAULT NULL,
                              `EmailAddress` varchar(50) DEFAULT NULL,
                              `IpAddress` varchar(50) DEFAULT NULL,
                              `StartDate` datetime DEFAULT NULL,
                              `EndDate` datetime DEFAULT NULL,
                              `anon_id` varchar(40) DEFAULT NULL,
                              `ext_id` varchar(40) DEFAULT NULL
                            ) ENGINE=MyISAM DEFAULT CHARSET=utf8;
                            """ )

        surveyMeta = (      """
                            CREATE TABLE `survey_meta` (
                              `SurveyId` varchar(50) DEFAULT NULL,
                              `SurveyCreationDate` datetime DEFAULT NULL,
                              `userfirstname` varchar(200) DEFAULT NULL,
                              `userlastname` varchar(200) DEFAULT NULL,
                              `surveyname` varchar(2000) DEFAULT NULL,
                              `SurveyOwnerId` varchar(50) DEFAULT NULL,
                              `SurveyExpirationDate` datetime DEFAULT NULL
                            ) ENGINE=MyISAM DEFAULT CHARSET=utf8;
                            """ )

        self.execute(choiceTbl)
        self.execute(questionTbl)
        self.execute(responseTbl)
        self.execute(responseMetaTbl)
        self.execute(surveyMeta)

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
        index = 0
        while index <= total:
            surveyID = surveys[index]['SurveyID']
            yield surveyID
            index += 1

    def __getSurvey(self, surveyID):
        '''
        Pull survey data for given surveyID from Qualtrics. Returns XML string.
        '''
        url="https://stanforduniversity.qualtrics.com//WRAPI/ControlPanel/api.php?API_SELECT=ControlPanel&Version=2.4&Request=getSurvey&User=%s&Token=%s&SurveyID=%s" % (self.apiuser, self.apitoken, surveyID)
        data = urllib2.urlopen(url).read()

        # Write data to temp file
        doc = open('temp.xml', 'w')
        doc.write(data)
        doc.close()

        # Parse XML from temp file, clean up and returns
        xml = ET.parse('temp.xml')
        os.remove('temp.xml')
        pxml = ET.tostring(xml, pretty_print=True)
        return pxml

    def __getResponses(self, surveyID):
        '''
        Pull response data for given surveyID from Qualtrics. Returns JSON object.
        '''
        url = "https://stanforduniversity.qualtrics.com/WRAPI/ControlPanel/api.php?API_SELECT=ControlPanel&Version=2.4&Request=getLegacyResponseData&User=%s&Token=%s&Format=JSON&SurveyID=%s&Labels=1" % (self.apiuser, self.apitoken, surveyID)
        data = json.loads(urllib2.urlopen(url).read())
        return data


## Helper methods for parsing data from raw Qualtrics exports

    def __getPodioID(self, surveyID):
        '''
        Given a surveyID from Qualtrics, finds embedded field 'c' and returns
        field value. For mapping surveys to course names via Podio project IDs.
        '''
        try:
            podioID = "NULL"
            survey = ET.fromstring(self.__getSurvey(surveyID))
            embeddedFields = survey.findall('./EmbeddedData/Field')
            for ef in embeddedFields:
                if ef.find('Name').text == 'c':
                    podioID = ef.find('Value').text
            return podioID
        except (urllib2.HTTPError, AttributeError) as e:
            # print "%s failed with error: %s" % (surveyID, e)
            return podioID # Method returns NULL if c field not found

## Transform methods

    def __parseSurveyMetadata(self, rawMeta):
        '''
        Given survey metadata for active user, returns a dict of dicts mapping
        column names to values for each survey.
        '''
        svMeta = dict()
        for idx, sv in enumerate(surveys):
            keys = ['SurveyID', 'SurveyName', 'SurveyCreationDate', 'UserFirstName', 'UserLastName', 'responses']
            data = dict()
            for key in keys:
                try:
                    data[key] = sv[key]
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
        svRaw = self.__getSurvey(svID)
        sv = ET.fromstring(svRaw)

        masterQ = dict()
        masterC = dict()

        # Parse data for each question
        questions = sv.findall('./Questions/Question')
        for idx, q in enumerate(questions):
            parsedQ = dict()
            qID = q.attrib['QuestionID']
            qkeys = ['ExportTag', 'Type', 'QuestionText', 'QuestionDescription', 'Validation/ForceResponse']
            parsedQ['SurveyID'] = svID
            parsedQ['QuestionID'] = qID
            for key in keys:
                try:
                    parsedq[key] = q.find(key).text
                except KeyError as k:
                    parsedq[k[0]] = 'NULL'
            masterQ[idx] = parsedQ

            # For each question, load all choices
            choices = q.findall('Choices/Choice')
            parsedC = dict()
            for c in choices:
                parsedC['SurveyID'] = svID
                parsedC['QuestionID'] = qID
                parsedC['ChoiceID'] = c.attrib['ID']
                cdesc = c.find('Description').text
                parsedC['Description'] = cdesc.replace("'", "''") if (cdesc is not None) else 'N/A'
            masterC[qID] = parsedC

        return masterQ, masterC

    def __parseResponses(self):
        pass

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
        a dict of dicts mapping column names to values.
        '''
        for row in data:
            query = "INSERT INTO %s(%s) VALUES (%s)" % (tableName, row.keys(), row.values())
            self.execute(query.encode('UTF-8', 'ignore'))


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
        self.__loadDB(parsedSM, 'survey_meta')

    def loadSurveyData(self):
        '''
        Client method extracts and transforms survey questions and question
        choices and loads to MySQL database using MySQLDB class methods.
        '''
        sids = self.__getSurveyIDs()
        for svID in sids:
            masterQ, masterC = self.__parseSurvey(svID)
            for parsedQ in masterQ.values():
                self.__loadDB(parsedQ, 'questions')
            for parsedC in masterC.values():
                self.__loadDB(parsedC, 'choices')

    def loadResponseData(self):
        '''
        Client method extracts and transforms response data and response metadata
        and loads to MySQL database using MySQLDB class methods.
        '''
        sids = self.__getSurveyIDs()
        for svID in sids:
            resp = self.__getResponses(svID)
            #TODO: Parse response metadata
            #TODO: Parse response data


#TODO: Specify and describe default behavior
if __name__ == '__main__':

    # Get survey data from Qualtrics
    qe = QualtricsExtractor()
    qe.setupDB()

    #TODO: Test loadSurveyMetadata and loadSurveyData methods. Check how long
    # parsing takes per survey and test on a smaller batch before running the
    # whole thing.

    # qe.loadSurveyMetadata()
    # qe.loadSurveyData()
