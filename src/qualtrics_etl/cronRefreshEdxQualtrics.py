from surveyextractor import QualtricsExtractor
from warnings import filterwarnings

# Script for scheduling regular EdxQualtrics updates
filterwarnings(action='ignore', category=Warning)
qe = QualtricsExtractor()
qe.setupDB()
qe.loadSurveyMetadata()
qe.loadSurveyData()
qe.loadResponseData()
