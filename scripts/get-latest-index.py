#!/usr/bin/python
import os, sys, getopt, json, csv
from urllib2 import urlopen

sys.path.insert(0, os.path.abspath('..'))
import awspricecalculator.common.consts as consts
import awspricecalculator.common.phelper as phelper

__location__ = os.path.dirname(os.path.realpath(__file__))
dataindexpath = os.path.join(os.path.split(__location__)[0],"awspricecalculator", "data")

"""
This script gets the latest index files from the AWS Price List API.
"""
#TODO: add support for term-type = onDemand, Reserved or both
def main(argv):

  SUPPORTED_SERVICES = (consts.SERVICE_S3, consts.SERVICE_EC2, consts.SERVICE_RDS, consts.SERVICE_LAMBDA,
                        consts.SERVICE_DYNAMODB, consts.SERVICE_KINESIS, consts.SERVICE_ALL)
  SUPPORTED_FORMATS = ('json','csv')
  OFFER_INDEX_URL = 'https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/{serviceIndex}/current/index.'
  
  service = ''
  format = ''
  region = ''

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
    if opt[0] in ("-r","--region"):
      region = opt[1]


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
          offerIndexUrl = OFFER_INDEX_URL.replace('{serviceIndex}',consts.SERVICE_INDEX_MAP[s]) + format
          print ('Downloading offerIndexUrl:['+offerIndexUrl+']...')

          servicedatapath = dataindexpath + "/" + s
          print ("servicedatapath:[{}]".format(servicedatapath))

          if not os.path.exists(servicedatapath): os.mkdir(servicedatapath)
          filename = servicedatapath+"/index."+format

          with open(filename, "w") as f: f.write(urlopen(offerIndexUrl).read())

          if format == 'csv':
            remove_metadata(filename)
            split_index(s, region)


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

"""
Some index files are too large. For example, the one for EC2 has more than 160K records.
In order to make price lookup more efficient, awspricecalculator splits the
index based on a combination of region, term type and product family. Each partition
has a key, which is used by tinydb to load smaller files as databases that can be
queried. This increases performance significantly.

"""

def split_index(service, region):
    #Split index format: region -> term type -> product family
    indexDict = {}#contains the keys of the files that will be created
    productFamilies = {}
    usageGroupings=[]
    partition_keys = phelper.get_partition_keys(region,'')#All regions and all term types (On-Demand + Reserved)
    for pk in partition_keys:
        indexDict[pk]=[]

    #print ("indexDict:[{}]".format(indexDict))

    fieldnames = []

    with open(get_index_file_name(service, 'index', 'csv'), 'rb') as csvfile:
        pricelist = csv.DictReader(csvfile, delimiter=',', quotechar='"')
        indexRegion = ''
        x = 0
        for row in pricelist:
            indexKey = ''
            if x==0: fieldnames=row.keys()
            if row.get('Location Type','') == 'AWS Region':
                indexRegion = row['Location']
            if row.get('Product Family','')== consts.PRODUCT_FAMILY_DATA_TRANSFER:
                indexRegion = row['From Location']

            #Determine the index partition the current row belongs to and append it to the corresponding array
            if row['TermType'] == consts.TERM_TYPE_RESERVED:
                #TODO:move the creation of the index dimensions to a common function
                if service == consts.SERVICE_EC2:
                    indexDimensions = (indexRegion,row['TermType'],row['Product Family'],row['OfferingClass'],row['Tenancy'], row['PurchaseOption'])
                elif service == consts.SERVICE_RDS:#'Tenancy' is not part of the RDS index, therefore default it to Shared
                    indexDimensions = (indexRegion,row['TermType'],row['Product Family'],row['OfferingClass'],row.get('Tenancy',consts.EC2_TENANCY_SHARED),row['PurchaseOption'])
            else:
                indexDimensions = (indexRegion,row['TermType'],row['Product Family'])

            indexKey = phelper.create_file_key(indexDimensions)
            if indexKey in indexDict:
                indexDict[indexKey].append(row)

            #Get a list of distinct product families in the index file
            productFamily = row['Product Family']
            if productFamily not in productFamilies:
                productFamilies[productFamily] = []
            usageGroup = row['Group']
            if usageGroup not in productFamilies[productFamily]:
                productFamilies[productFamily].append(usageGroup)

            x += 1

    print ("productFamilies:{}".format(productFamilies))

    i = 0
    #Create csv files based on the partitions that were calculated when scanning the main index.csv file
    for f in indexDict.keys():
        if indexDict[f]:
            i += 1
            print "Writing file for key: [{}]".format(f)
            with open(get_index_file_name(service, f, 'csv'),'w') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames, dialect='excel', quoting=csv.QUOTE_ALL)
                writer.writeheader()
                for r in indexDict[f]:
                    writer.writerow(r)

    print ("Number of records in main index file: [{}]".format(x))
    print "Number of files written: [{}]".format(i)


def get_index_file_name(service, name, format):
  result = '../awspricecalculator/data/'+service+'/'+name+'.'+format
  return result












if __name__ == "__main__":
   main(sys.argv[1:])
