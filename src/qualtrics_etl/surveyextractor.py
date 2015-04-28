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

    def getSurveyMetadata(self):
        '''
        Pull survey metadata from Qualtrics.
        '''
        url = "https://stanforduniversity.qualtrics.com/WRAPI/ControlPanel/api.php?API_SELECT=ControlPanel&Version=2.4&Request=getSurveys&User=%s&Token=%s&Format=JSON&JSONPrettyPrint=1" % (self.user, self.token)
        d = urllib2.urlopen(url).read()
        data = json.loads(d)
        return data

    def genSurveyIDs(self, data):
        '''
        Generator for Qualtrics survey IDs.
        '''
        surveys = data['Result']['Surveys']
        total = len(surveys)
        index = 0
        while index <= total:
            surveyID = surveys[index]['SurveyID']
            yield surveyID
            index += 1

    def getSurvey(self, surveyID):
        '''
        Pull survey data for given surveyID from Qualtrics.
        '''
        url="https://stanforduniversity.qualtrics.com//WRAPI/ControlPanel/api.php?API_SELECT=ControlPanel&Version=2.4&Request=getSurvey&User=%s&Token=%s&SurveyID=%s" % (self.user, self.token, surveyID)
        data = urllib2.urlopen(url).read()
        return data



if __name__ == '__main__':
    qe = QualtricsExtractor()
    surveys = qe.getSurveyMetadata()
    sids = qe.genSurveyIDs(surveys)
    srv = qe.getSurvey(sids.next())

    doc = open('temp.xml', 'w')
    doc.write(srv)
    doc.close()

    data = ET.parse('temp.xml')
    os.remove('temp.xml')
    print ET.tostring(data, pretty_print=True)
