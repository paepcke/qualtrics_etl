from surveyextractor import QualtricsExtractor
from warnings import filterwarnings

# Script for scheduling regular EdxQualtrics updates
filterwarnings('ignore', '*')
qe = QualtricsExtractor()
qe.setupDB()
qe.loadSurveyMetadata()
qe.loadSurveyData()
qe.loadResponseData()
