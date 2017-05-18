#!/usr/bin/python
import os, sys, getopt, json, csv
from urllib2 import urlopen

sys.path.insert(0, os.path.abspath('..'))
import pricecalculator.common.consts as consts
import pricecalculator.common.phelper as phelper


def main(argv):

  SUPPORTED_SERVICES = ('s3', 'ec2','rds','lambda', 'all')
  SUPPORTED_FORMATS = ('json','csv')
  SERVICE_INDEX_MAP = {'s3':'AmazonS3', 'ec2':'AmazonEC2', 'rds':'AmazonRDS','lambda':'AWSLambda'} #TODO:use consts instead
  OFFER_INDEX_URL = 'https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/{serviceIndex}/current/index.'
  
  service = ''
  format = ''

  help_message = 'Script usage: \nget-latest-index.py --service=<s3|ec2|rds|etc> --format=<csv|json>'

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


  if not format: format = 'csv'

  validation_ok = True


  if service not in SUPPORTED_SERVICES:
    validation_ok = False
  if format not in SUPPORTED_FORMATS:
    validation_ok = False

  if not validation_ok:
    print (help_message)
    sys.exit(2)

  services = []
  if service == 'all': services = SUPPORTED_SERVICES
  else: services = [service]

  for s in services:
      if s != 'all':
          offerIndexUrl = OFFER_INDEX_URL.replace('{serviceIndex}',SERVICE_INDEX_MAP[s]) + format
          print ('Downloading offerIndexUrl:['+offerIndexUrl+']...')

          #TODO: add validation, if data dir doesn't exist, create it
          filename = "../pricecalculator/data/"+s+"/index."+format

          with open(filename, "w") as f: f.write(urlopen(offerIndexUrl).read())

          if format == 'csv':
            remove_metadata(filename)
            split_index(s)


"""
The first rows in the PriceList index.csv are metadata.
This method removes the metadata from the index files and writes it in a separate .json file,
 so the metadata can be accessed by other modules. For example, the PriceList Version is returned
 in every price calculation.
"""

def remove_metadata(index_filename):
  print "Removing metadata from file [{}]".format(index_filename)
  metadata_filename = index_filename.replace('.csv','_metadata.json')
  metadata_dict = {}
  with open(index_filename,"r") as rf:
    lines = rf.readlines()
  with open(index_filename,"w") as wf:
    i = 0
    for l in lines:
      #The first 5 records in the CSV file are metadata
      if i <= 4:
        config_record = l.replace('","','"|"').strip("\n").split("|")
        metadata_dict[config_record[0].strip('\"')] = config_record[1].strip('\"')
      else:
        wf.write(l)
      i += 1
  with open(metadata_filename,"w") as mf:
    print "Creating metadata file [{}]".format(metadata_filename)
    metadata_json = json.dumps(metadata_dict,sort_keys=False,indent=4)
    print "metadata_json: [{}]".format(metadata_json)
    mf.write(metadata_json)



def split_index(service):


    #Split index format: region -> term type -> product family
    indexDict = {}
    partition_keys = phelper.get_partition_keys('')
    for pk in partition_keys:
        indexDict[pk]=[]

    fieldnames = []

    with open(get_index_file_name(service, 'index', 'csv'), 'rb') as csvfile:
        pricelist = csv.DictReader(csvfile, delimiter=',', quotechar='"')
        indexRegion = ''
        x = 0
        for row in pricelist:
            indexKey = ''
            if x==0: fieldnames=row.keys()
            if 'Location Type' in row:
                if row['Location Type'] == 'AWS Region':
                    indexRegion = row['Location']
            if 'Product Family' in row:
                if row['Product Family']== consts.PRODUCT_FAMILY_DATA_TRANSFER:
                    indexRegion = row['From Location']
            indexKey = phelper.create_file_key(indexRegion,row['TermType'],row['Product Family'])
            if indexKey in indexDict:
                indexDict[indexKey].append(row)
            x += 1

    #print "metadata: {}".format(metadata)

    i = 0
    for f in indexDict.keys():
        if indexDict[f]:
            i += 1
            print "Writing file for key: [{}]".format(f)
            with open(get_index_file_name(service, f, 'csv'),'w') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                for r in indexDict[f]:
                    writer.writerow(r)

    print "Number of files written: [{}]".format(i)




def get_index_file_name(service, name, format):
  result = '../pricecalculator/data/'+service+'/'+name+'.'+format
  return result












if __name__ == "__main__":
   main(sys.argv[1:])
