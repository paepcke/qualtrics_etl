#!/usr/bin/env bash

USAGE="Usage: $(basename $0) surveyId"

#*****USER_NAME=dataman
USER_NAME=paepcke

if [ $# -lt 1 ]
then
    echo $USAGE
    exit 1
fi

SURVEY_ID=$1

TMPFILE=$(mktemp /tmp/survey_${SURVEY_ID}_scrubbed)

#*********
#echo "tmpfile: ${TMPFILE}"
#exit
#*********

# Ensure the temp file is deleted on exit:
trap "rm -f $TMPFILE" EXIT

read -rd '' SELECT_CMD <<EOF
SELECT 'SurveyId','ResponseId','QuestionNumber','AnswerChoiceId','Description'
UNION ALL
SELECT *
  INTO OUTFILE '${TMPFILE}'
  FIELDS TERMINATED BY "," OPTIONALLY ENCLOSED BY '"' LINES TERMINATED BY '\n'
  FROM EdxQualtrics.response
  WHERE surveyId = ${SURVEY_ID}
    AND QuestionNumber = 'contents'
     OR QuestionNumber = 'shortplans'
     OR QuestionNumber = 'longplans';
EOF


mysql --login-path=${USER_NAME} EdxQualtrics -e "${SELECT_CMD}" > $TMPFILE

$(dirname $0)/../../anonymizer/src/anonymizer/anonymize_csv.py --infile ${TMPFILE} --ignorecol 1 2 3

