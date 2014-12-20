import json
import urllib2
from pymysql_utils1 import MySQLDB
import xml.etree.ElementTree as ET
from urllib2 import Request, URLError
from os.path import expanduser
import os.path
import sys

"""
Returns User, Token pair by parsing the file qualtrics_user and qualtrics_token
in the ~/.ssh directory.
"""
def getUserPwd():
  home = expanduser("~")
  userFile = home + '/.ssh/qualtrics_user'  
  tokenFile = home + '/.ssh/qualtrics_token'
  if os.path.isfile(userFile) == False:
    sys.exit("User file not found " + userFile) 
  if os.path.isfile(tokenFile) == False:
    sys.exit("Token file not found " + tokenFile) 

  uid = None
  token = None  

  with open(userFile, 'r') as f:
    uid = f.readline()

  with open(tokenFile, 'r') as f:
    token = f.readline()
  
  return uid.strip(), token.strip()

_User,_Token = getUserPwd()
print _User, _Token

db=MySQLDB('127.0.0.1',3306,'root','','EdxQualtrics')


"""
{u'Meta': {u'Status': u'Success', u'Debug': u''}, u'Result': {u'Surveys': [{u'SurveyCreationDate': u'2014-10-27 15:08:19', u'responses': u'3', u'UserFirstName': u'jagadish', u'SurveyType': u'SV', u'LastModified': u'2014-11-04 12:50:51', u'LastActivated': u'2014-10-27 15:21:36', u'SurveyName': u'cs140-feedback', u'UserLastName': u'venkatraman', u'SurveyID': u'SV_6YegHjmjmngyhVz', u'SurveyStatus': u'Active', u'CreatorID': u'UR_elipjMDGVTxcjZz', u'SurveyStartDate': u'0000-00-00 00:00:00', u'SurveyOwnerID': u'UR_elipjMDGVTxcjZz', u'SurveyExpirationDate': u'0000-00-00 00:00:00'}]}}
Returns all surveys for a particular user, token pair
"""
def getSurveysForUser (User, Token):
  url='https://stanforduniversity.qualtrics.com/WRAPI/ControlPanel/api.php?API_SELECT=ControlPanel&Version=2.4&Request=getSurveys&User=%s&Token=%s&Format=JSON&JSONPrettyPrint=1'%(User,Token)
  print url
  d=None
  try:
    d=urllib2.urlopen(url).read()
  except URLError as e:
    if hasattr(e, 'reason'):
        print 'We failed to reach a server.'
        print 'Reason: ', e.reason
    elif hasattr(e, 'code'):
        print 'The server couldn\'t fulfill the request.'
        print 'Error code: ', e.code
    return None
    # everything is fine

  dict=json.loads(d)
  print dict
  return dict

"""
Returns all details corresponding to a survey. Fires up a request to the qualtrics
getSurvey() API and returns the raw XML. The format of the XML is specific to qualtrics
"""
def getSurvey (User, Token, SurveyID):
  'SV_6YegHjmjmngyhVz'
  url="https://stanforduniversity.qualtrics.com//WRAPI/ControlPanel/api.php?API_SELECT=ControlPanel&Version=2.4&Request=getSurvey&User=%s&Token=%s&SurveyID=%s"%(User,Token, SurveyID)
  print url
  d=None
  try:
    d=urllib2.urlopen(url).read()
  except URLError as e:
    if hasattr(e, 'reason'):
        print 'We failed to reach a server.'
        print 'Reason: ', e.reason
    elif hasattr(e, 'code'):
        print 'The server couldn\'t fulfill the request.'
        print 'Error code: ', e.code
    return None


  print d
  return d

"""
Obtains all responses corresponding to a survey
Both elaborate_response and condensed_response response-types are supported.
"""
def getResponses (User, Token, SurveyID):
  url="""https://stanforduniversity.qualtrics.com/WRAPI/ControlPanel/api.php?API_SELECT=ControlPanel&Version=2.4&Request=getLegacyResponseData&User=%s&Token=%s&Format=JSON&SurveyID=%s&Labels=1"""%(User, Token, SurveyID)
  print url
  try:
    elaborate_response=json.loads(urllib2.urlopen(url).read())
  except URLError as e:
    if hasattr(e, 'reason'):
        print 'We failed to reach a server.'
        print 'Reason: ', e.reason
    elif hasattr(e, 'code'):
        print 'The server couldn\'t fulfill the request.'
        print 'Error code: ', e.code
    return None, None


  print 'ELABORATE RESPONSE'
  print elaborate_response

  print 'CONDENSED RESPONSE'

  url="""https://stanforduniversity.qualtrics.com/WRAPI/ControlPanel/api.php?API_SELECT=ControlPanel&Version=2.4&Request=getLegacyResponseData&User=%s&Token=%s&Format=JSON&SurveyID=%s"""%(User, Token, SurveyID)  
  print url

  try:
    condensed_response=json.loads(urllib2.urlopen(url).read())
  except URLError as e:
    if hasattr(e, 'reason'):
        print 'We failed to reach a server.'
        print 'Reason: ', e.reason
    elif hasattr(e, 'code'):
        print 'The server couldn\'t fulfill the request.'
        print 'Error code: ', e.code
    return None, None


  print condensed_response

  return (elaborate_response,condensed_response)

"""
Transformation function Transform(x): returns x if x is not None, 
                              returns 'NULL' if x is None
"""
def Transform(x):
  if x is None:
    return '"NULL"'
  return x

def Q(x):
    if x is None:
        return x

    try:
      s = str(x)
    except :
      s = ''

    s = s.replace('"','""')
    s = s.replace ("'",'""')
    s = '"%s"'%(s)
    return s



"""
Parses the responses and extracts fields like ip, name, anon etc from the response.
Also parses responses and inserts each response to a question in the DB
"""
def parseResponses (SurveyID):
  responses, condensed_responses = getResponses(_User, _Token, SurveyID)
  if responses == None or condensed_responses == None:
      return
  if (not(isinstance(responses,dict))):
      return

  responseIds = responses.keys()

  for responseId in responseIds:
    response = responses[responseId]
    ip=response['IPAddress']
    name=response['Name']
    end=response['EndDate']
    email=response['EmailAddress']
    ext_id = ''
    if 'a' in response:
      ext_id = response['a']
    start=response['StartDate']
    print ext_id
    query = "insert into response_metadata(SurveyId, Name, EmailAddress, IpAddress, StartDate, EndDate,  ext_id, anon_id) values\
    ('%s','%s','%s','%s','%s','%s','%s',idExt2Anon('%s'))"%(Q(SurveyID),Q(name),Q(email),Q(ip),start,end, ext_id, ext_id)
    print query
    db.execute(query)
    if (not(isinstance(response,dict))):
      continue

    keys = response.keys()
    for key in keys:
      print key
      print response

      if key and key[0]=='Q' and '_' in key[0]:
        splits = key[0].split('_')
        #qid = key[0]
        qid = splits[0]
        cid = splits[1]
        ans = response[key]
        query = "insert into response(SurveyId, ResponseId, QuestionId, AnswerChoiceId,Description) values \
         ('%s','%s','%s','%s')" % (Q(SurveyID), Q(responseId), Q(qid), Q(cid),Q(ans))
        print query
        db.execute (query)



      if key and key[0]=='Q':
        qid = key
        ans = response[key]
        query = "insert into response(SurveyId, ResponseId, QuestionId, Description) values \
         ('%s','%s','%s','%s')" % (Q(SurveyID), Q(responseId), Q(qid), Q(ans))
        print query
        db.execute (query)




"""
Driver for executing the program, that parses the survey questions and loads the Survey
responses
"""

d=getSurveysForUser (_User, _Token)  

if d == None:
  print 'no surveys found for user %s' %(_User)

print d
res = d['Result']
if 'Surveys' not in res:
	raise  Exception('ERROR. Surveys is not in results')
surveys = res['Surveys']
for survey in surveys:
  q="insert into survey_meta(SurveyId, SurveyCreationDate, UserFirstName, UserLastName, SurveyName, SurveyOwnerId, SurveyExpirationDate) values\
  ('%s','%s','%s','%s','%s','%s','%s') "%(Q(survey['SurveyID']),survey['SurveyCreationDate'],Q(survey['UserFirstName']),Q(survey['UserLastName']),Q(survey['SurveyName']),Q(survey['SurveyOwnerID']),survey['SurveyExpirationDate'])
  db.execute(q)
  x=getSurvey(_User,_Token,survey['SurveyID'])
  
  if x == None:
    continue

  sid = survey['SurveyID']
  root = ET.fromstring(x)
  questionElements = root.findall('./Questions/Question')
  for q in questionElements:
    qid=q.attrib['QuestionID']
    type_=q.find('Type').text
    text=q.find('QuestionText').text
    desc=q.find('QuestionDescription').text
    forceElem = q.find('Validation/ForceResponse')
    if forceElem is not None:  
      force=q.find('Validation/ForceResponse').text
    else:
      force = 'False'  

    query= "insert into question(SurveyId, QuestionId, QuestionText, QuestionDescription, ForceResponse, Questiontype) values ('%s','%s','%s','%s','%s','%s')\
    "%(sid, qid, Q(text), Q(desc), force, type_)
    print query
    db.execute(query)
    choices = q.findall('Choices/Choice')
    for choice in choices:
       cid = choice.attrib['ID']
       cdesc = choice.find('Description').text
       cdesc=cdesc.replace("'","''")
       query= "insert into choice(SurveyId, QuestionId, ChoiceId, Description) values ('%s','%s','%s','%s')"%(sid, qid, cid, Q(cdesc))
       print query
       db.execute(query)

  parseResponses(sid)


