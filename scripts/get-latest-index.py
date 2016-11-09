#!/usr/bin/python
import sys, getopt
from urllib2 import urlopen


def main(argv):

  SUPPORTED_REGIONS = ('us-east-1')
  SUPPORTED_SERVICES = ('s3', 'ec2','rds')
  SUPPORTED_FORMATS = ('json','csv')
  SERVICE_INDEX_MAP = {'s3':'AmazonS3', 'ec2':'AmazonEC2', 'rds':'AmazonRDS'}
  OFFER_INDEX_URL = 'https://pricing.{region}.amazonaws.com/offers/v1.0/aws/{serviceIndex}/current/index.'
  
  region = 'us-east-1'
  service = ''
  format = ''

  help_message = 'Script usage: \nget-latest-index.py --service=<s3|ec2|rds|etc>'

  try:
    opts, args = getopt.getopt(argv,"hr:s:f:",["region=","service=","format="])
    print ('opts: ' + str(opts))
  except getopt.GetoptError:
    print (help_message)
    sys.exit(2)

  for opt in opts:
    if opt[0] == '-h':
      print (help_message)
      sys.exit()
    if opt[0] in ("-s","--service"):
      service = opt[1]
    if opt[0] in ("-f","--format"):
      format = opt[1]


  if not format: format = 'json'

  validation_ok = True

  if service not in SUPPORTED_SERVICES:
    validation_ok = False
  if region not in SUPPORTED_REGIONS:
    validation_ok = False
  if format not in SUPPORTED_FORMATS:
    validation_ok = False

  if not validation_ok:
    print (help_message)
    sys.exit(2)

  offerIndexUrl = OFFER_INDEX_URL.replace('{region}',region)
  offerIndexUrl = offerIndexUrl.replace('{serviceIndex}',SERVICE_INDEX_MAP[service]) + format
  print ('Downloading offerIndexUrl:['+offerIndexUrl+']...')

  with open("../pricecalculator/"+service+"/index."+format, "w") as f: f.write(urlopen(offerIndexUrl).read())



if __name__ == "__main__":
   main(sys.argv[1:])
