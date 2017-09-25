import json
import consts, models
import datetime

from ..ec2 import pricing as ec2pricing
from ..s3 import pricing as s3pricing
from ..rds import pricing as rdspricing
from ..awslambda import pricing as lambdapricing
from ..dynamodb import pricing as ddbpricing
from ..kinesis import pricing as kinesispricing



#Creates a table with all the SKUs that are part of the total price
def buildSkuTable(evaluated_sku_desc):
  result = {}
  sorted_descriptions = sorted(evaluated_sku_desc)
  result_table_header = "Price | Description | Price Per Unit | Usage | Rate Code"
  result_records = ""
  total = 0
  for s in sorted_descriptions:
    result_records = result_records + "$" + str(s[0]) + "|" + str(s[1]) + "|" + str(s[2]) + "|" + str(s[3]) + "|" + s[4]+"\n"
    total = total + s[0]
  
  result['header']=result_table_header
  result['records']=result_records
  result['total']=total
  return result



#It calculates price based on a variable price dimension. For example: by region, os, instance type, etc.
def compare(**kwargs):
  service = kwargs['service']
  sortCriteria = kwargs['sortCriteria']
  result = []
  cheapest_price = 0
  criteria_array = ()
  kwargs_key = ""
  
  #Sort by AWS Region - Total Cost and To-region (for sorting by destination - find which regions are cheaper for backups)
  if sortCriteria in [consts.SORT_CRITERIA_REGION, consts.SORT_CRITERIA_TO_REGION]:
    tableCriteriaHeader = "Sorted by total cost by region\nRegion code\tRegion name\t"
    if sortCriteria == consts.SORT_CRITERIA_TO_REGION:
      tableCriteriaHeader = "Sorted by data transfer destination from region ["+kwargs['region']+"] to other regions\nTo-Region code\tTo-Region name\t"

    for r in consts.SUPPORTED_REGIONS:
      if sortCriteria == consts.SORT_CRITERIA_TO_REGION:
        kwargs['toRegion']=r
      else:
        kwargs['region']=r
      if service == consts.SERVICE_EC2:
        p = ec2pricing.calculate(models.Ec2PriceDimension(**kwargs))
      if service == consts.SERVICE_S3:
        p = s3pricing.calculate(models.S3PriceDimension(**kwargs))
      if service == consts.SERVICE_RDS:
        p = rdspricing.calculate(models.RdsPriceDimension(**kwargs))
      if service == consts.SERVICE_LAMBDA:
        p = lambdapricing.calculate(models.LambdaPriceDimension(**kwargs))
      if service == consts.SERVICE_DYNAMODB:
        p = ddbpricing.calculate(models.DynamoDBPriceDimension(**kwargs))
      if service == consts.SERVICE_KINESIS:
        p = kinesispricing.calculate(models.KinesisPriceDimension(**kwargs))


      print (json.dumps(p, indent=True))
      #Only append records for those combinations that exist in the PriceList API
      if p['pricingRecords']: result.append((p['totalCost'],r))


 #Sort by EC2 Operating System
  if sortCriteria == consts.SORT_CRITERIA_OS:
    tableCriteriaHeader = "Total cost sorted by Operating System in region ["+kwargs['region']+"]\nOS\t"
    for o in consts.SUPPORTED_EC2_OPERATING_SYSTEMS:
      kwargs['operatingSystem']=o
      if service == consts.SERVICE_EC2:
        p = ec2pricing.calculate(models.Ec2PriceDimension(**kwargs))

      result.append((p['totalCost'],o))

  #Sort by RDS DB Instance Class
  if sortCriteria == consts.SORT_CRITERIA_DB_INSTANCE_CLASS:
    tableCriteriaHeader = "Total cost sorted by DB Instance Class in region ["+kwargs['region']+"]\nDB Instance Class\t"
    for ic in consts.SUPPORTED_RDS_INSTANCE_CLASSES:
      kwargs['dbInstanceClass']=ic
      p = rdspricing.calculate(models.RdsPriceDimension(**kwargs))
      result.append((p['totalCost'],ic))

  #Sort by RDS DB Engine
  if sortCriteria == consts.SORT_CRITERIA_DB_ENGINE:
    tableCriteriaHeader = "Total cost sorted by DB Engine in region ["+kwargs['region']+"]\nDB Engine\t"
    for e in consts.RDS_SUPPORTED_DB_ENGINES:
      kwargs['engine']=e
      p = rdspricing.calculate(models.RdsPriceDimension(**kwargs))
      result.append((p['totalCost'],e))


  #Sort by Lambda memory
  if sortCriteria == consts.SORT_CRITERIA_LAMBDA_MEMORY:
    tableCriteriaHeader = "Total cost sorted Allocated Memory in region ["+kwargs['region']+"]\nMemory\t"
    for m in consts.LAMBDA_MEM_SIZES:
      kwargs['memoryMb']=m
      p = lambdapricing.calculate(models.LambdaPriceDimension(**kwargs))
      if p['pricingRecords']: result.append((p['totalCost'],m))


  #Sort by S3 Storage Class
  if sortCriteria == consts.SORT_CRITERIA_S3_STORAGE_CLASS:
    #TODO: Use criteria_array for all sort calculations
    tableCriteriaHeader = "Tocal cost sorted by S3 Storage Class in region ["+kwargs['region']+"]\nStorage Class\t"
    criteria_array = consts.SUPPORTED_S3_STORAGE_CLASSES
    for c in criteria_array:
      kwargs['storageClass']=c
      p = s3pricing.calculate(models.S3PriceDimension(**kwargs))
      if p['pricingRecords']: result.append((p['totalCost'],c))
  

  sorted_result = sorted(result)
  print ("sorted_result: {}".format(sorted_result))
  if sorted_result: cheapest_price = sorted_result[0][0]
  result = []
  i = 0
  #TODO: use a structured object (Class or dict) instead of using indexes for each field in the table
  for r in sorted_result:
    if sorted_result[i][0]>0:
      #Calculate the current record relative to the last record
      delta_last = 0
      pct_to_last = 0
      pct_to_cheapest = 0
      if i >= 1:
        delta_last = sorted_result[i][0]-sorted_result[i-1][0]
        if sorted_result[i-1][0] > 0:
          pct_to_last = ((sorted_result[i][0]-sorted_result[i-1][0])/sorted_result[i-1][0])*100
      if cheapest_price > 0:
        pct_to_cheapest = ((r[0]-cheapest_price)/cheapest_price)*100

      result.append((r[0], r[1],pct_to_cheapest, pct_to_last,(r[0]-cheapest_price),delta_last))

    i = i+1

  print("Sorted cost table:")
  print(tableCriteriaHeader+"Cost(USD)\t% compared to cheapest\t% compared to previous\tdelta cheapest\tdelta previous")
  for r in result:
    rowCriteriaValues = ""
    if sortCriteria in [consts.SORT_CRITERIA_REGION, consts.SORT_CRITERIA_TO_REGION]:
      rowCriteriaValues = r[1]+"\t"+consts.REGION_MAP[r[1]]+"\t"
    else:
      rowCriteriaValues = str(r[1])+"\t"
    print(rowCriteriaValues+str(r[0])+"\t"+str(r[2])+"\t"+str(r[3])+"\t"+str(r[4])+"\t"+str(r[5]))



  return result


def get_index_file_name(service, name, format):
  result = '../awspricecalculator/'+service+'/data/'+name+'.'+format
  return result







