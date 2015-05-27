from .surveyextractor import QualtricsExtractor

# Script for scheduling regular EdxQualtrics updates
qe = QualtricsExtractor()
qe.setupDB()
qe.loadSurveyMetadata()
qe.loadSurveyData()
qe.loadResponseData()
