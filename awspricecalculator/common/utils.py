import json, logging
import consts, models
import datetime

from ..ec2 import pricing as ec2pricing
from ..s3 import pricing as s3pricing
from ..rds import pricing as rdspricing
from ..awslambda import pricing as lambdapricing
from ..dynamodb import pricing as ddbpricing
from ..kinesis import pricing as kinesispricing
from errors import NoDataFoundError

log = logging.getLogger()

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
#TODO:include sortCriteria in the parameters for this function, instead of having it in kwargs (which are meant for priceDimensions only)
def compare(**kwargs):
  service = kwargs['service']
  sortCriteria = kwargs['sortCriteria']
  result = []
  cheapest_price = 0
  criteria_array = ()
  kwargs_key = ""
  origkwargs = kwargs #we'll keep track of the original paramaters
  scenarioArray = []



  #Sort by AWS Region - Total Cost and To-region (for sorting by destination - find which regions are cheaper for backups)
  if sortCriteria in [consts.SORT_CRITERIA_REGION, consts.SORT_CRITERIA_TO_REGION]:
    tableCriteriaHeader = "Sorted by total cost by region\nRegion code\tRegion name\t"
    if sortCriteria == consts.SORT_CRITERIA_TO_REGION:
      tableCriteriaHeader = "Sorted by data transfer destination from region ["+kwargs['region']+"] to other regions\nTo-Region code\tTo-Region name\t"

    for r in consts.SUPPORTED_REGIONS:
      kwargs = dict(origkwargs)  #revert to original parameters at the beginning of each loop
      if sortCriteria == consts.SORT_CRITERIA_TO_REGION:
        kwargs['toRegion']=r
      else:
        kwargs['region']=r

      #avoid a situation where source and origin destinations are the same for dataTransferOutInterRegionGb
      if kwargs.get('dataTransferOutInterRegionGb',0) > 0 and kwargs['region'] == kwargs['toRegion']:
        kwargs.pop('dataTransferOutInterRegionGb',0)

      try:
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

      except NoDataFoundError:
        continue

      log.debug ("PricingResult: [{}]".format(json.dumps(p, indent=4)))
      #Only append records for those combinations that exist in the PriceList API
      if p['pricingRecords']: result.append((p['totalCost'],r,p))

 #Sort by EC2 Instance Type
  if sortCriteria == consts.SORT_CRITERIA_EC2_INSTANCE_TYPE:
    tableCriteriaHeader = "Total cost sorted by EC2 Instance Type in region ["+kwargs['region']+"]\nType\t"
    instanceTypes = kwargs.get('instanceTypes','')
    if instanceTypes: instanceTypes = instanceTypes.split(',')
    else: instanceTypes=consts.SUPPORTED_INSTANCE_TYPES
    log.info("instanceTypes: [{}]".format(instanceTypes))
    for t in instanceTypes:
      kwargs['instanceType']=t
      try:
        p = ec2pricing.calculate(models.Ec2PriceDimension(**kwargs))
        result.append((p['totalCost'],t,p))
      except NoDataFoundError:
        pass

 #Sort by EC2 Operating System
  if sortCriteria == consts.SORT_CRITERIA_OS:
    tableCriteriaHeader = "Total cost sorted by Operating System in region ["+kwargs['region']+"]\nOS\t"
    for o in consts.SUPPORTED_EC2_OPERATING_SYSTEMS:
      kwargs['operatingSystem']=o
      try:
        p = ec2pricing.calculate(models.Ec2PriceDimension(**kwargs))
        result.append((p['totalCost'],o,p))
      except NoDataFoundError:
        pass


  #Sort by RDS DB Instance Class
  if sortCriteria == consts.SORT_CRITERIA_DB_INSTANCE_CLASS:
    tableCriteriaHeader = "Total cost sorted by DB Instance Class in region ["+kwargs['region']+"]\nDB Instance Class\t"
    for ic in consts.SUPPORTED_RDS_INSTANCE_CLASSES:
      kwargs['dbInstanceClass']=ic
      try:
        p = rdspricing.calculate(models.RdsPriceDimension(**kwargs))
        result.append((p['totalCost'],ic,p))
      except NoDataFoundError:
        pass

  #Sort by RDS DB Engine
  if sortCriteria == consts.SORT_CRITERIA_DB_ENGINE:
    tableCriteriaHeader = "Total cost sorted by DB Engine in region ["+kwargs['region']+"]\nDB Engine - License Model\t"
    for e in consts.RDS_SUPPORTED_DB_ENGINES:
      kwargs['engine']=e
      for lm in consts.RDS_SUPPORTED_LICENSE_MODELS:
        if 'sqlserver' in e or 'oracle' in e:
          kwargs['licenseModel']=lm
        else:
          #SCRIPT_RDS_LICENSE_MODEL_PUBLIC is the only applicable license model for open source engines
          if lm == consts.SCRIPT_RDS_LICENSE_MODEL_PUBLIC: kwargs['licenseModel'] = consts.SCRIPT_RDS_LICENSE_MODEL_PUBLIC
          else: continue
        try:
          p = rdspricing.calculate(models.RdsPriceDimension(**kwargs))
          result.append((p['totalCost'],"{} - {}".format(e,lm),p))
        except NoDataFoundError:
          pass


  #Sort by Lambda memory
  if sortCriteria == consts.SORT_CRITERIA_LAMBDA_MEMORY:
    tableCriteriaHeader = "Total cost sorted Allocated Memory in region ["+kwargs['region']+"]\nMemory\t"
    for m in consts.LAMBDA_MEM_SIZES:
      kwargs['memoryMb']=m
      p = lambdapricing.calculate(models.LambdaPriceDimension(**kwargs))
      if p['pricingRecords']: result.append((p['totalCost'],m,p))


  #Sort by S3 Storage Class
  if sortCriteria == consts.SORT_CRITERIA_S3_STORAGE_CLASS:
    #TODO: Use criteria_array for all sort calculations
    tableCriteriaHeader = "Tocal cost sorted by S3 Storage Class in region ["+kwargs['region']+"]\nStorage Class\t"
    criteria_array = consts.SUPPORTED_S3_STORAGE_CLASSES
    for c in criteria_array:
      kwargs['storageClass']=c
      try:
        p = s3pricing.calculate(models.S3PriceDimension(**kwargs))
        if p['pricingRecords']: result.append((p['totalCost'],c,p))
      except NoDataFoundError:
        pass

  #Sort by S3 Storage Size (this implies that a comma-separated list of values is supplied for storage-size-gb
  if sortCriteria == consts.SORT_CRITERIA_S3_STORAGE_SIZE_GB:
    tableCriteriaHeader = "Tocal cost sorted by S3 Storage Size (GB) in region ["+kwargs['region']+"]\nStorage Size GB\t"
    criteria_array = kwargs.get('storageSizeGb','').split(consts.SORT_CRITERIA_VALUE_SEPARATOR)
    for c in criteria_array:
      kwargs['storageSizeGb']=int(c)
      try:
        p = s3pricing.calculate(models.S3PriceDimension(**kwargs))
        if p['pricingRecords']: result.append((p['totalCost'],c,p))
      except NoDataFoundError:
        pass

  #Sort by S3 Data Retrieval GB (this implies that a comma-separated list of values is supplied for data-retrieval-gb)
  #For now, it excludes data transfer out to the internet. #TODO: include a parameter for data transfer out, proportional to data retrieval
  if sortCriteria == consts.SORT_CRITERIA_S3_DATA_RETRIEVAL_GB:
    tableCriteriaHeader = "Tocal cost sorted by S3 Data Retrieval (GB) for Storage Class [{}] in region [{}]\nData Retrieval GB\t".format(kwargs['storageClass'],kwargs['region'])
    criteria_array = kwargs.get('dataRetrievalGb','').split(consts.SORT_CRITERIA_VALUE_SEPARATOR)
    for c in criteria_array:
      kwargs['dataRetrievalGb']=int(c)
      try:
        p = s3pricing.calculate(models.S3PriceDimension(**kwargs))
        if p['pricingRecords']: result.append((p['totalCost'],c,p))
      except NoDataFoundError:
        pass


  #Sort by S3 Data Retrieval GB AND Storage Class (this implies that a comma-separated list of values is supplied for data-retrieval-gb)
  #For now, it excludes data transfer out to the internet. #TODO: include a parameter for data transfer out, proportional to data retrieval
  if sortCriteria == consts.SORT_CRITERIA_S3_STORAGE_CLASS_DATA_RETRIEVAL_GB:
    tableCriteriaHeader = "Tocal cost sorted by S3 Data Retrieval (GB) and all Storage Classes in region [{}]\nStorage Class + Data Retrieval GB\t".format(kwargs['region'])
    criteria_array = kwargs.get('dataRetrievalGb','').split(consts.SORT_CRITERIA_VALUE_SEPARATOR)
    for sc in consts.SUPPORTED_S3_STORAGE_CLASSES:
      for c in criteria_array:
        kwargs['storageClass'] = sc
        kwargs['dataRetrievalGb']=int(c)
        try:
          p = s3pricing.calculate(models.S3PriceDimension(**kwargs))
          if p['pricingRecords']: result.append((p['totalCost'],"{}_{}GB".format(sc,c),p))
        except NoDataFoundError:
          pass

  sorted_result = sorted(result)
  log.debug ("sorted_result: {}".format(sorted_result))
  if sorted_result: cheapest_price = sorted_result[0][0]
  result = []
  i = 0
  awsPriceListApiVersion = ''
  pricingScenarios = []
  #TODO: use a structured object (Class or dict) instead of using indexes for each field in the table
  for r in sorted_result:
    if i == 0: awsPriceListApiVersion = r[2]['awsPriceListApiVersion']
    if sorted_result[i][0]>0:
      #Calculate the current record relative to the last record
      delta_cheapest = r[0]-cheapest_price
      delta_last = 0
      pct_to_last = 0
      pct_to_cheapest = 0
      if i >= 1:
        delta_last = sorted_result[i][0]-sorted_result[i-1][0]
        if sorted_result[i-1][0] > 0:
          pct_to_last = ((sorted_result[i][0]-sorted_result[i-1][0])/sorted_result[i-1][0])*100
      if cheapest_price > 0:
        pct_to_cheapest = ((r[0]-cheapest_price)/cheapest_price)*100


      result.append((r[0], r[1],pct_to_cheapest, pct_to_last,delta_cheapest,delta_last))

      #TODO:populate price dimensions in PricingScenario instance
      pricingScenario = models.PricingScenario(i, r[1], {}, r[2], r[0], sortCriteria)
      pricingScenario.deltaCheapest = delta_cheapest
      pricingScenario.deltaPrevious = delta_last
      pricingScenario.pctToCheapest = pct_to_cheapest
      pricingScenario.pctToPrevious = pct_to_last
      pricingScenarios.append(pricingScenario.__dict__)

    i = i+1

  pricecomparison = models.PriceComparison(awsPriceListApiVersion, service, sortCriteria)
  pricecomparison.pricingScenarios = pricingScenarios

  print("Sorted cost table:")
  print(tableCriteriaHeader+"Cost(USD)\t% compared to cheapest\t% compared to previous\tdelta cheapest\tdelta previous")
  for r in result:
    rowCriteriaValues = ""
    if sortCriteria in [consts.SORT_CRITERIA_REGION, consts.SORT_CRITERIA_TO_REGION]:
      rowCriteriaValues = r[1]+"\t"+consts.REGION_MAP[r[1]]+"\t"
    else:
      rowCriteriaValues = str(r[1])+"\t"
    print(rowCriteriaValues+str(r[0])+"\t"+str(r[2])+"\t"+str(r[3])+"\t"+str(r[4])+"\t"+str(r[5]))

  return pricecomparison.__dict__


def compare_term_types(service, **kwargs):
  log.info("kwargs:[{}]".format(kwargs))
  years = kwargs['years']
  regions = []
  if kwargs.get('regions',[]): regions = kwargs['regions']
  else: regions = [kwargs['region']]
  kwargs.pop('sortCriteria','')
  scenarioArray = []
  priceCalc = {}
  calcKey = ''
  awsPriceListApiVersion = ""
  onDemandTotal = 0

  #TODO: move this logic to models.TermPricingAnalysis
  #Iterate through applicable combinations of term types, purchase options and years
  termTypes = kwargs.get('termTypes',consts.SUPPORTED_TERM_TYPES)
  purchaseOptions = kwargs.get('purchaseOptions',consts.EC2_SUPPORTED_PURCHASE_OPTIONS)
  offeringClasses = kwargs.get('offeringClasses',consts.SUPPORTED_EC2_OFFERING_CLASSES)
  for r in regions:
    kwargs['region'] = r
    for t in termTypes:
      i = 0
      for oc in offeringClasses:
        for p in purchaseOptions:
          addFlag = False
          kwargs['instanceHours'] = 365 * 24 * int(kwargs['instanceCount']) * int(years)
          kwargs['termType']=t

          if t == consts.SCRIPT_TERM_TYPE_RESERVED:
            if len(regions)>1: calcKey = "{}-{}-{}-{}-{}yr".format(r,t,oc,p,years)
            else: calcKey = "{}-{}-{}-{}yr".format(t,oc,p,years)
            kwargs['offeringType']=p
            kwargs['offeringClass']=oc
            if p == consts.SCRIPT_EC2_PURCHASE_OPTION_ALL_UPFRONT: kwargs.pop('instanceHours',0)
            addFlag = True
          if t == consts.SCRIPT_TERM_TYPE_ON_DEMAND and i == 0:#only calculate price once for OnDemand
            if len(regions)>1: calcKey = "{}-{}-{}yr".format(r,t,years)
            else: calcKey = "{}-{}yr".format(t,years)
            kwargs['offeringType']=''
            addFlag = True
          i += 1
          try:
            #This flag ensures there are no duplicate OnDemand entries
            pdims = {}
            priceCalc = {}
            if addFlag:
              if service == consts.SERVICE_EC2:
                pdims = models.Ec2PriceDimension(**kwargs)
                pdims.region=r
                priceCalc = ec2pricing.calculate(pdims)
              elif service == consts.SERVICE_RDS:
                pdims = models.RdsPriceDimension(**kwargs)
                pdims.region=r
                priceCalc = rdspricing.calculate(pdims)
              log.info("priceCalc: {}".format(json.dumps(priceCalc, indent=4)))
              #pricingScenario = models.TermPricingScenario(calcKey, dict(kwargs), priceCalc['pricingRecords'], priceCalc['totalCost'], onDemandTotal)
              if t == consts.SCRIPT_TERM_TYPE_ON_DEMAND: onDemandTotal = priceCalc['totalCost']
              pricingScenario = models.TermPricingScenario(calcKey, pdims.__dict__, priceCalc['pricingRecords'], priceCalc['totalCost'], onDemandTotal)
              scenarioArray.append([pricingScenario.totalCost,pricingScenario])

              awsPriceListApiVersion = priceCalc['awsPriceListApiVersion']

          except NoDataFoundError as ndf:
            log.debug ("NoDataFoundError pdims:[{}]".format(pdims))


  if len(scenarioArray)==0: raise NoDataFoundError("NoDataFoundeError for term type comparison [{}]: [{}]".format(kwargs))
  sortedPricingScenarios = calculate_sorted_results(scenarioArray)
  #print "calculation results:[{}]".format(json.dumps(sortedPricingScenarios, indent=4))

  pricingAnalysis = models.TermPricingAnalysis(awsPriceListApiVersion, regions, service, years)
  pricingAnalysis.pricingScenarios = sortedPricingScenarios
  #TODO: move the next 3 calls to a single method
  pricingAnalysis.calculate_months_to_recover()
  pricingAnalysis.calculate_monthly_breakdown()
  pricingAnalysis.get_csv_data()
  return pricingAnalysis.__dict__



#TODO: use for sortCriteria calculations too (so we only have this logic once)
#TODO: modify such that items in unsortedScenarioArray are not a tuple, but simply a pricingScenario object
def calculate_sorted_results(unsortedScenarioArray):

  sorted_result = sorted(unsortedScenarioArray)
  if sorted_result: cheapest_price = sorted_result[0][0]
  result = []
  i = 0
  for r in sorted_result:
    #print "sorting the following pricing scenario:[{}]".format(json.dumps(r[1].__dict__, indent=4))
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

      pricingScenario = r[1]
      pricingScenario.index = i
      pricingScenario.deltaPrevious = round(delta_last,2)
      pricingScenario.deltaCheapest = round(r[0]-cheapest_price,2)
      pricingScenario.pctToPrevious = round(pct_to_last,2)
      pricingScenario.pctToCheapest = round(pct_to_cheapest,2)
      pricingScenario.calculateOnDemandSavings()
      result.append(pricingScenario.__dict__)

    i = i+1

  return result



def get_index_file_name(service, name, format):
  result = '../awspricecalculator/'+service+'/data/'+name+'.'+format
  return result







