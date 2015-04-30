import json
import urllib2
from os.path import expanduser
import os.path
import sys
from lxml import etree as ET

class QualtricsExtractor(object):

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

        self.user = None
        self.token = None

        with open(userFile, 'r') as f:
            self.user = f.readline().rstrip()

        with open(tokenFile, 'r') as f:
            self.token = f.readline().rstrip()


## API extractor methods

    def __getSurveyMetadata(self):
        '''
        Pull survey metadata from Qualtrics. Returns JSON object.
        '''
        url = "https://stanforduniversity.qualtrics.com/WRAPI/ControlPanel/api.php?API_SELECT=ControlPanel&Version=2.4&Request=getSurveys&User=%s&Token=%s&Format=JSON&JSONPrettyPrint=1" % (self.user, self.token)
        data = json.loads(urllib2.urlopen(url).read())
        return data

    def __genSurveyIDs(self):
        '''
        Generator for Qualtrics survey IDs.
        '''
        data = self.__getSurveyMetadata
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
        url="https://stanforduniversity.qualtrics.com//WRAPI/ControlPanel/api.php?API_SELECT=ControlPanel&Version=2.4&Request=getSurvey&User=%s&Token=%s&SurveyID=%s" % (self.user, self.token, surveyID)
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
        url = "https://stanforduniversity.qualtrics.com/WRAPI/ControlPanel/api.php?API_SELECT=ControlPanel&Version=2.4&Request=getLegacyResponseData&User=%s&Token=%s&Format=JSON&SurveyID=%s&Labels=1" % (self.user, self.token, surveyID)
        data = json.loads(urllib2.urlopen(url).read())
        return data


## Helper methods for survey parsing

    def __getPodioID(self, surveyID):
        try:
            podioID = "N/A"
            survey = ET.fromstring(self.__getSurvey(surveyID))
            embeddedFields = survey.findall('./EmbeddedData/Field')
            for ef in embeddedFields:
                if ef.find('Name').text == 'c':
                    podioID = ef.find('Value').text
            return podioID
        except (urllib2.HTTPError, AttributeError) as e:
            print surveyID
            print e


## Convenience methods to write data to outfiles

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


## Client file IO methods

    def writeRaw_SurveyMetadata(self):
        '''
        Client method outputs survey metadata to JSON file.
        '''
        svMeta = self.__getSurveyMetadata()
        self.__writeJSON(svMeta, "SV_meta")

    #TODO: Test this method
    def writeRaw_Survey(self, num=1):
        '''
        Client method outputs specified number of surveys to XML files. Default
        value is 1; user can also specify "all" to pull all surveys.
        '''
        sids = self.__genSurveyIDs()
        svTotal = len(sids)
        if (num == 'all' or num > svTotal):
            num = svTotal
        index = 0
        while index < num:
            svID = sids.next()
            sv = self.__getSurvey(svID)
            self.__writeXML(sv, svID)
            index += 1

    # TODO: delete this method if above method works as specified
    def writeRaw_AllSurveys(self):
        '''
        Client method outputs all available surveys to XML files.
        '''
        svIDs = self.__genSurveyIDs()
        for svID in svIDs:
            sv = self.__getSurvey(svID)
            self.__writeXML(sv, svID)

    # TODO: for human readable output, makes more sense to do all-in-one?
    def writeRaw_OneSurveyResponses(self):
        '''
        Client method outputs responses for one survey to JSON file.
        '''
        svID = self.__genSurveyIDs().next()
        resp = self.__getResponses(svID)
        fn = svID + "_responses"
        self.__writeJSON(resp, fn)


## Client data transformation methods

    def getParsedSurveyMetadata(self):
        '''
        Client method returns dict of relevant survey metadata.
        '''
        # Pull relevant data from Qualtrics.
        svMeta = self.__getSurveyMetadata()
        surveys = svMeta['Result']['Surveys']

        # For each survey, parse relevant data into new dict.
        data = dict()
        for sv in surveys:
            fields = dict()
            try:
                fields['SurveyID'] = sv['SurveyID']
                fields['PodioID'] = self.__getPodioID(sv['SurveyID'])
                fields['SurveyName'] = sv['SurveyName']
                fields['SurveyCreationDate'] = sv['SurveyCreationDate']
                fields['UserFirstName'] = sv['UserFirstName']
                fields['UserLastName'] = sv['UserLastName']
                fields['responses'] = sv['responses']
            except KeyError as k:
                fields[k[0]] = 'NULL'

            # Finally, add entry to data dict.
            data[sv['SurveyID']] = fields
        self.__writeJSON(data, 'out')

    def getParsedSurveys(self):
        #TODO: implement
        pass

    def getParsedResponseMetadata(self):
        #TODO: implement
        pass

    def getParsedResponses(self):
        #TODO: implement
        pass


#TODO: describe default behavior
if __name__ == '__main__':

    # Get survey data from Qualtrics
    qe = QualtricsExtractor()

    qe.getParsedSurveyMetadata()
