#!/usr/bin/python
import sys, os, getopt, json, logging
import argparse
import traceback
sys.path.insert(0, os.path.abspath('..'))

import awspricecalculator.redshift.pricing as redshiftpricing
import awspricecalculator.common.consts as consts
import awspricecalculator.common.models as data
import awspricecalculator.common.utils as utils
from awspricecalculator.common.errors import ValidationError
from awspricecalculator.common.errors import NoDataFoundError

log = logging.getLogger()
logging.basicConfig()
log.setLevel(logging.DEBUG)

def main(argv):

  parser = argparse.ArgumentParser()
  parser.add_argument('--region', help='', required=False)
  parser.add_argument('--regions', help='', required=False)
  parser.add_argument('--sort-criteria', help='', required=False)
  parser.add_argument('--instance-type', help='', required=False)
  parser.add_argument('--instance-types', help='', required=False)
  parser.add_argument('--instance-hours', help='', type=int, required=False)
  parser.add_argument('--ebs-volume-type', help='', required=False)
  parser.add_argument('--ebs-storage-gb-month', help='', required=False)
  parser.add_argument('--piops', help='', type=int, required=False)
  parser.add_argument('--data-transfer-out-internet-gb', help='', required=False)
  parser.add_argument('--data-transfer-out-intraregion-gb', help='', required=False)
  parser.add_argument('--data-transfer-out-interregion-gb', help='', required=False)
  parser.add_argument('--to-region', help='', required=False)
  parser.add_argument('--term-type', help='', required=False)
  parser.add_argument('--offering-class', help='', required=False)
  parser.add_argument('--offering-classes', help='', required=False)
  parser.add_argument('--instance-count', help='', type=int, required=False)
  parser.add_argument('--years', help='', required=False)
  parser.add_argument('--offering-type', help='', required=False)
  parser.add_argument('--offering-types', help='', required=False)

  if len(sys.argv) == 1:
    parser.print_help()
    sys.exit(1)
  args = parser.parse_args()

  region = ''
  regions = ''
  instanceType = ''
  instanceTypes = ''
  instanceHours = 0
  instanceCount = 0
  sortCriteria = ''
  ebsVolumeType = ''
  ebsStorageGbMonth = 0
  pIops = 0
  dataTransferOutInternetGb = 0
  dataTransferOutIntraRegionGb = 0
  dataTransferOutInterRegionGb = 0
  toRegion = ''
  termType = consts.SCRIPT_TERM_TYPE_ON_DEMAND
  offeringClass = ''
  offeringClasses = consts.SUPPORTED_REDSHIFT_OFFERING_CLASSES #only used for Reserved comparisons (standard, convertible)
  offeringType = ''
  offeringTypes = consts.EC2_SUPPORTED_PURCHASE_OPTIONS #only used for Reserved comparisons (all-upfront, partial-upfront, no-upfront)
  years = 1

  if args.region: region = args.region
  if args.regions: regions = args.regions
  if args.sort_criteria: sortCriteria = args.sort_criteria
  if args.instance_type: instanceType = args.instance_type
  if args.instance_types: instanceTypes = args.instance_types
  if args.instance_hours: instanceHours = int(args.instance_hours)
  if args.ebs_volume_type: ebsVolumeType = args.ebs_volume_type
  if args.ebs_storage_gb_month: ebsStorageGbMonth = int(args.ebs_storage_gb_month)
  if args.piops: pIops = int(args.piops)
  if args.data_transfer_out_internet_gb: dataTransferOutInternetGb = int(args.data_transfer_out_internet_gb)
  if args.data_transfer_out_intraregion_gb: dataTransferOutIntraRegionGb = int(args.data_transfer_out_intraregion_gb)
  if args.data_transfer_out_interregion_gb: dataTransferOutInterRegionGb = int(args.data_transfer_out_interregion_gb)
  if args.to_region: toRegion = args.to_region
  if args.term_type: termType = args.term_type
  if args.offering_class: offeringClass = args.offering_class
  if args.offering_classes: offeringClasses = args.offering_classes.split(',')
  if args.instance_count: instanceCount = args.instance_count
  if args.offering_type: offeringType = args.offering_type
  if args.offering_types: offeringTypes = args.offering_types.split(',')
  if args.years: years = str(args.years)

  #TODO: Implement comparison between a subset of regions by entering an array of regions to compare
  #TODO: Implement a sort by target region (for data transfer)
  #TODO: For Reserved pricing, include a payment plan throughout the whole period, and a monthly average and savings

  #TODO: remove EBS for Redshift


  try:

    kwargs = {'sortCriteria':sortCriteria, 'instanceType':instanceType, 'instanceTypes':instanceTypes,
              'instanceHours':instanceHours, 'dataTransferOutInternetGb':dataTransferOutInternetGb, 'pIops':pIops,
              'dataTransferOutIntraRegionGb':dataTransferOutIntraRegionGb, 'dataTransferOutInterRegionGb':dataTransferOutInterRegionGb,
              'toRegion':toRegion, 'termType':termType, 'instanceCount': instanceCount, 'years': years, 'offeringType':offeringType,
              'offeringClass':offeringClass
            }

    if region: kwargs['region'] = region

    if sortCriteria:
      if sortCriteria in (consts.SORT_CRITERIA_TERM_TYPE, consts.SORT_CRITERIA_TERM_TYPE_REGION):
        if sortCriteria == consts.SORT_CRITERIA_TERM_TYPE_REGION:
          #TODO: validate that region list is comma-separated
          #TODO: move this list to utils.compare_term_types
          if regions: kwargs['regions'] = regions.split(',')
          else: kwargs['regions']=consts.SUPPORTED_REGIONS
        kwargs['purchaseOptions'] = offeringTypes  #purchase options are referred to as offering types in the EC2 API
        kwargs['offeringClasses']=offeringClasses
        validate (kwargs)
        termPricingAnalysis = utils.compare_term_types(service=consts.SERVICE_REDSHIFT, **kwargs)
        tabularData = termPricingAnalysis.pop('tabularData')
        print ("Redshift termpPricingAnalysis: [{}]".format(json.dumps(termPricingAnalysis,sort_keys=False, indent=4)))
        print("csvData:\n{}\n".format(termPricingAnalysis['csvData']))
        print("tabularData:\n{}".format(tabularData))

      else:
        validate (kwargs)
        pricecomparisons = utils.compare(service=consts.SERVICE_REDSHIFT,**kwargs)
        print("Price comparisons:[{}]".format(json.dumps(pricecomparisons, indent=4)))
    else:
      validate (kwargs)
      redshift_pricing = redshiftpricing.calculate(data.RedshiftPriceDimension(**kwargs))
      print(json.dumps(redshift_pricing,sort_keys=False,indent=4))



  except NoDataFoundError as ndf:
    print ("NoDataFoundError args:[{}]".format(args))

  except Exception as e:
    traceback.print_exc()
    print("Exception message:["+str(e)+"]")


"""
This function contains validations at the script level. No need to validate Redshift parameters, since
class RedshiftPriceDimension already contains a validation function.
"""
def validate (args):
  #TODO: add - if termType sort criteria is specified, don't include offeringClass (singular)
  #TODO: add - if offeringTypes is included, have at least one valid offeringType (purchase option)
  #TODO: move to models or a common place that can be used by both CLI and API
  validation_msg = ""
  if args.get('sortCriteria','') == consts.SORT_CRITERIA_TERM_TYPE:
    if args.get('instanceHours',False):
      validation_msg = "instance-hours cannot be set when sort-criteria=term-type"
    if args.get('offeringType',False):
      validation_msg = "offering-type cannot be set when sort-criteria=term-type - try offering-types (plural) instead"
    if not args.get('years',''):
      validation_msg = "years cannot be empty"
  if args.get('sortCriteria','') == consts.SORT_CRITERIA_TERM_TYPE_REGION:
    if not args.get('offeringClasses',''):
      validation_msg = "offering-classes cannot be empty"
    if not args.get('purchaseOptions',''):
      validation_msg = "offering-types cannot be empty"

  if validation_msg:
      print("Error: [{}]".format(validation_msg))
      raise ValidationError(validation_msg)

  return

if __name__ == "__main__":
   main(sys.argv[1:])
