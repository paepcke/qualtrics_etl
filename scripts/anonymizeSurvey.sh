#!/usr/bin/env bash

# Given a Qualtrics survey ID, read all
# responses for that ID from table 
# EdxQualtrics.response, scrubbing the
# open-text columns of personally identifiable
# information.
#
# To test: 
#
# In script below, temporarily change the value of MYSQL_DB to Misc
#
# Do the following in MySQL:
#
#     CREATE TABLE Misc.response like EdxQualtrics.response;
#     INSERT INTO response VALUES(123,456,'longplans','This is my good answer','My good description'),
#                                (123,456,'shortplans','This is my 650-723-9684 phone answer','My 94025 zip description'),
#                                (123,456,'contents','This is my paepcke@cs.stanford.edu email answer','My 94025-4310 zip description');
#
# Then in shell:
#
#     cd <qualtrics_etl_proj_root>
#     scripts/anonymizeSurvey.sh SV_7V8mngUZSEUIKhL 123
#
# Observe output. First line should be unchanged. In lines
# 2 and 3 the phone number, two zip codes, and one email
# address should be redacted, i.e. replaced with an obvious
# placeholder (<phoneRedac>,...)


USAGE="Usage: $(basename $0) surveyId"

USER_NAME=dataman
MYSQL_DB=EdxQualtrics
MYSQL_TBL_NAME=response


if [ $# -lt 1 ]
then
    echo $USAGE
    exit 1
fi

SURVEY_ID=$1

# mktemp kept giving me 'Not enough X's...' error.
# So screw it:
#TMPFILE=$(mktemp /tmp/survey${SURVEY_ID}scrubbed_xxxxxxxxxxxxxxx)
TMPFILE=/tmp/survey_${SURVEY_ID}_scrubbed_$(date +%s).csv

#*********
#echo "tmpfile: ${TMPFILE}"
#exit
#*********

# Ensure the temp file is deleted on exit.
# Commented out, b/c of MySQL ownership:
# trap "echo 'Attempt to remove tempfile; may need to do manually with sudo'; rm -f $TMPFILE" EXIT

read -rd '' SELECT_CMD <<EOF
SELECT 'SurveyId','ResponseId','QuestionNumber','AnswerChoiceId','Description'
UNION ALL
SELECT *
  INTO OUTFILE '${TMPFILE}'
  FIELDS TERMINATED BY "," OPTIONALLY ENCLOSED BY '"' LINES TERMINATED BY '\n'
  FROM ${MYSQL_TBL_NAME}
  WHERE surveyId = '${SURVEY_ID}'
    AND QuestionNumber = 'contents'
     OR QuestionNumber = 'shortplans'
     OR QuestionNumber = 'longplans';
EOF

#***********
#echo $SELECT_CMD
#exit
#***********

mysql --login-path=${USER_NAME} ${MYSQL_DB} -e "${SELECT_CMD}"

$(dirname $0)/../../anonymizer/src/anonymizer/anonymize_csv.py --infile ${TMPFILE} --ignorecol 0 1 2

