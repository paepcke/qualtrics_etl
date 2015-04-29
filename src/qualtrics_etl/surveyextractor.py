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

    def __getSurveyMetadata(self):
        '''
        Pull survey metadata from Qualtrics.
        '''
        url = "https://stanforduniversity.qualtrics.com/WRAPI/ControlPanel/api.php?API_SELECT=ControlPanel&Version=2.4&Request=getSurveys&User=%s&Token=%s&Format=JSON&JSONPrettyPrint=1" % (self.user, self.token)
        data = urllib2.urlopen(url).read()
        return data

    def __genSurveyIDs(self, data):
        '''
        Generator for Qualtrics survey IDs.
        '''
        d = json.loads(data)
        surveys = d['Result']['Surveys']
        total = len(surveys)
        index = 0
        while index <= total:
            surveyID = surveys[index]['SurveyID']
            yield surveyID
            index += 1

    def __getSurvey(self, surveyID):
        '''
        Pull survey data for given surveyID from Qualtrics.
        '''
        url="https://stanforduniversity.qualtrics.com//WRAPI/ControlPanel/api.php?API_SELECT=ControlPanel&Version=2.4&Request=getSurvey&User=%s&Token=%s&SurveyID=%s" % (self.user, self.token, surveyID)
        data = urllib2.urlopen(url).read()
        return data

    def __writeXML(self, data, filename):
        '''
        Convenience function for writing out XML data to file.
        '''
        # Write data to temp file
        doc = open('temp.xml', 'w')
        doc.write(data)
        doc.close()

        # Parse XML file
        xml = ET.parse('temp.xml')
        os.remove('temp.xml')
        pxml = ET.tostring(xml, pretty_print=True)

        # Write parsed XML to outfile
        filename = "xml/" + filename + ".xml"
        srv = open(filename, 'w')
        srv.write(pxml)
        srv.close()

    def writeOneSurvey(self):
        '''
        Client method outputs one survey to XML file.
        '''
        svMeta = self.__getSurveyMetadata()
        svID = self.__genSurveyIDs(svMeta).next()
        sv = self.__getSurvey(svID)
        self.__writeXML(sv, svID)

    def writeAllSurveys(self):
        '''
        Client method outputs all available surveys to XML files.
        '''
        svMeta = self.__getSurveyMetadata()
        svIDs = self.__genSurveyIDs(svMeta)
        for svID in svIDs:
            sv = self.__getSurvey(svID)
            self.__writeXML(sv, svID)

    def writeMetadata(self):
        '''
        Client method outputs survey metadata to JSON file.
        '''
        svMeta = self.__getSurveyMetadata()
        doc = open("xml/SV_meta.json", 'w')
        doc.write(svMeta)
        doc.close()

# Default behavior for class pulls a single survey from Qualtrics and outputs as
# pretty-printed XML. TODO: Pull all surveys.

if __name__ == '__main__':

    # Get survey data from Qualtrics
    qe = QualtricsExtractor()
    qe.writeMetadata()
    qe.writeOneSurvey()