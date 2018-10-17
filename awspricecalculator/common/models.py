import math, logging
import consts
from errors import ValidationError

log = logging.getLogger()

class ElbPriceDimension():
    def __init__(self, hours, dataProcessedGb):
        self.hours = hours
        self.dataProcessedGb = dataProcessedGb



class S3PriceDimension():
    def __init__(self, **kwargs):
          self.region = ''
          self.termType = consts.SCRIPT_TERM_TYPE_ON_DEMAND
          self.storageClass = ''
          self.storageSizeGb = 0

          #TODO:Implement requestType and requestNumber as <requestType>Count, such that a single call to the price calculator can account for multiple request types
          self.requestType = ''
          self.requestNumber = 0

          self.dataRetrievalGb = 0
          self.dataTransferOutInternetGb = 0

          self.region = kwargs.get('region','')
          self.storageClass = kwargs.get('storageClass','')
          self.storageSizeGb = int(kwargs.get('storageSizeGb',0))
          self.requestType = kwargs.get('requestType','')
          self.requestNumber = int(kwargs.get('requestNumber',0))
          self.dataRetrievalGb = int(kwargs.get('dataRetrievalGb',0))
          self.dataTransferOutInternetGb = int(kwargs.get('dataTransferOutInternetGb',0))

          self.validate()


    def validate(self):
      validation_ok = True
      validation_message = ""

      if not self.storageClass:
        validation_message += "Storage class cannot be empty\n"
        validation_ok = False
      if self.storageClass and self.storageClass not in consts.SUPPORTED_S3_STORAGE_CLASSES:
        validation_message += "Invalid storage class:[{}]\n".format(self.storageClass)
        validation_ok = False
      if self.region not in consts.SUPPORTED_REGIONS:
        validation_message += "Invalid region:[{}]\n".format(self.region)
        validation_ok = False
      if self.requestNumber and not self.requestType:
        validation_message += "requestType cannot be empty if you specity requestNumber\n"
        validation_ok = False
      if self.requestType and self.requestType not in consts.SUPPORTED_REQUEST_TYPES:
        validation_message += "Invalid request type:[{}]\n".format(self.requestType)
        validation_ok = False

      if not validation_ok:
          raise ValidationError(validation_message)

      return validation_ok




class Ec2PriceDimension():
    def __init__(self, **kargs):

      self.region = kargs['region']
      self.termType = kargs.get('termType',consts.SCRIPT_TERM_TYPE_ON_DEMAND)
      self.instanceType = kargs.get('instanceType','')
      self.operatingSystem = kargs.get('operatingSystem',consts.SCRIPT_OPERATING_SYSTEM_LINUX)
      self.instanceHours = int(kargs.get('instanceHours',0))

      #TODO: Add support for pre-installed software (i.e. SQL Web in Windows instances)
      self.preInstalledSoftware = 'NA'

      #TODO: Add support for different license models
      self.licenseModel = consts.SCRIPT_EC2_LICENSE_MODEL_NONE_REQUIRED
      if self.operatingSystem == consts.SCRIPT_OPERATING_SYSTEM_WINDOWS:
          self.licenseModel = consts.SCRIPT_EC2_LICENSE_MODEL_NONE_REQUIRED
      if self.operatingSystem == consts.SCRIPT_OPERATING_SYSTEM_WINDOWS_BYOL:
          self.licenseModel = consts.SCRIPT_EC2_LICENSE_MODEL_BYOL

      #Reserved Instances
      self.offeringClass = kargs.get('offeringClass',consts.SCRIPT_EC2_OFFERING_CLASS_STANDARD)
      if not self.offeringClass: self.offeringClass = consts.SCRIPT_EC2_OFFERING_CLASS_STANDARD
      self.instanceCount = int(kargs.get('instanceCount',0))
      self.offeringType = kargs.get('offeringType','')
      self.years = int(kargs.get('years',1))

      #Data Transfer
      self.dataTransferOutInternetGb = int(kargs.get('dataTransferOutInternetGb',0))
      self.dataTransferOutIntraRegionGb = int(kargs.get('dataTransferOutIntraRegionGb',0))
      self.dataTransferOutInterRegionGb = int(kargs.get('dataTransferOutInterRegionGb',0))
      self.toRegion = kargs.get('toRegion','')

      #Storage
      self.pIops = int(kargs.get('pIops',0))
      self.storageMedia = ''
      self.ebsVolumeType = kargs.get('ebsVolumeType','')
      if self.ebsVolumeType in consts.EBS_VOLUME_TYPES_MAP: self.storageMedia = consts.EBS_VOLUME_TYPES_MAP[self.ebsVolumeType]['storageMedia']
      self.volumeType = ''
      if self.ebsVolumeType in consts.EBS_VOLUME_TYPES_MAP:  self.volumeType = consts.EBS_VOLUME_TYPES_MAP[self.ebsVolumeType]['volumeType']
      if not self.volumeType: self.volumeType = consts.SCRIPT_EBS_VOLUME_TYPE_GP2
      self.ebsStorageGbMonth = int(kargs.get('ebsStorageGbMonth',0))
      self.ebsSnapshotGbMonth = int(kargs.get('ebsSnapshotGbMonth',0))

      #Elastic Load Balancer (classic)
      self.elbHours = int(kargs.get('elbHours',0))
      self.elbDataProcessedGb = int(kargs.get('elbDataProcessedGb',0))

      #Application Load Balancer
      self.albHours = int(kargs.get('albHours',0))
      self.albLcus= int(kargs.get('albLcus',0))

      #TODO: add support for Network Load Balancer

      #TODO: Add support for shared and dedicated tenancies
      self.tenancy = consts.SCRIPT_EC2_TENANCY_SHARED

      self.validate()

    def validate(self):
      validation_message = ""

      if self.instanceType and self.instanceType not in consts.SUPPORTED_INSTANCE_TYPES:
        validation_message += "instance-type is "+self.instanceType+", must be one of the following values:"+str(consts.SUPPORTED_INSTANCE_TYPES)
      if self.region not in consts.SUPPORTED_REGIONS:
        validation_message += "region is "+self.region+", must be one of the following values:"+str(consts.SUPPORTED_REGIONS)
      if not self.operatingSystem:
        validation_message += "operating-system cannot be empty\n"
      if self.operatingSystem and self.operatingSystem not in consts.SUPPORTED_EC2_OPERATING_SYSTEMS:
        validation_message += "operating-system is "+self.operatingSystem+", must be one of the following values:"+str(consts.SUPPORTED_EC2_OPERATING_SYSTEMS)
      if self.ebsVolumeType and self.ebsVolumeType not in consts.SUPPORTED_EBS_VOLUME_TYPES:
        validation_message += "ebs-volume-type is "+self.ebsVolumeType+", must be one of the following values:"+str(consts.SUPPORTED_EBS_VOLUME_TYPES)
      if self.dataTransferOutInterRegionGb > 0 and not self.toRegion:
        validation_message += "Must specify a to-region if you specify data-transfer-out-interregion-gb\n"
      if self.dataTransferOutInterRegionGb and self.toRegion not in consts.SUPPORTED_REGIONS:
        validation_message += "to-region is "+self.toRegion+", must be one of the following values:"+str(consts.SUPPORTED_REGIONS)
      if self.dataTransferOutInterRegionGb and self.region == self.toRegion:
        validation_message += "source and destination regions must be different for inter-regional data transfers\n"
      if self.termType not in consts.SUPPORTED_TERM_TYPES:
          validation_message += "term-type is "+self.termType+", must be one of the following values:[{}]".format(consts.SUPPORTED_TERM_TYPES)
      if self.termType == consts.SCRIPT_TERM_TYPE_RESERVED:
          if not self.offeringClass:
              validation_message += "offering-class must be specified for Reserved instances\n"
          if self.offeringClass and self.offeringClass not in (consts.SUPPORTED_EC2_OFFERING_CLASSES):
              validation_message += "offering-class is "+self.offeringClass+", must be one of the following values:"+str(consts.SUPPORTED_EC2_OFFERING_CLASSES)
          if not self.offeringType:
              validation_message += "offering-type must be specified\n"
          if self.offeringType and self.offeringType not in (consts.EC2_SUPPORTED_PURCHASE_OPTIONS):
              validation_message += "offering-type is "+self.offeringType+", must be one of the following values:"+str(consts.EC2_SUPPORTED_PURCHASE_OPTIONS)
          if self.offeringType == consts.SCRIPT_EC2_PURCHASE_OPTION_ALL_UPFRONT and self.instanceHours:
              validation_message += "instance-hours cannot be set if term-type=reserved and offering-type=all-upfront\n"
          if self.offeringType == consts.SCRIPT_EC2_PURCHASE_OPTION_ALL_UPFRONT and not self.instanceCount:
              validation_message += "instance-count is mandatory if term-type=reserved and offering-type=all-upfront\n"
          if not self.years:
              validation_message += "years cannot be empty for Reserved instances"

      #TODO: add validation for max number of IOPS
      #TODO: add validation for negative numbers

      validation_ok = True
      if validation_message:
          raise ValidationError(validation_message)

      return validation_ok



class RdsPriceDimension():
    def __init__(self, **kargs):
      self.region = kargs.get('region','')

      #DB Instance
      self.dbInstanceClass = kargs.get('dbInstanceClass','')
      self.engine = kargs.get('engine')

      self.licenseModel = kargs.get('licenseModel')
      if self.engine in (consts.SCRIPT_RDS_DATABASE_ENGINE_MYSQL,consts.SCRIPT_RDS_DATABASE_ENGINE_POSTGRESQL,
                         consts.SCRIPT_RDS_DATABASE_ENGINE_AURORA_MYSQL, consts.SCRIPT_RDS_DATABASE_ENGINE_AURORA_POSTGRESQL):
          self.licenseModel = consts.SCRIPT_RDS_LICENSE_MODEL_PUBLIC

      self.instanceHours = int(kargs.get('instanceHours',0))

      self.multiAz = kargs.get('multiAz',False)
      if self.multiAz:
        self.deploymentOption = consts.RDS_DEPLOYMENT_OPTION_MULTI_AZ
      else:
        self.deploymentOption = consts.RDS_DEPLOYMENT_OPTION_SINGLE_AZ

      #OnDemand vs. Reserved
      self.termType = kargs.get('termType',consts.SCRIPT_TERM_TYPE_ON_DEMAND)
      self.offeringClass = consts.SCRIPT_EC2_OFFERING_CLASS_STANDARD #TODO: add support for others, besides 'standard'
      if not self.offeringClass: self.offeringClass = consts.SCRIPT_EC2_OFFERING_CLASS_STANDARD
      self.offeringType = kargs.get('offeringType','')
      self.instanceCount = int(kargs.get('instanceCount',0))
      self.years = int(kargs.get('years',1))

      #Data Transfer
      self.dataTransferOutInternetGb = kargs.get('dataTransferOutInternetGb',0)
      self.dataTransferOutIntraRegionGb = kargs.get('dataTransferOutIntraRegionGb',0)
      self.dataTransferOutInterRegionGb = kargs.get('dataTransferOutInterRegionGb',0)
      self.toRegion = kargs.get('toRegion','')

      #Storage
      self.storageGbMonth = int(kargs.get('storageGbMonth',0))
      self.storageType = kargs.get('storageType','')
      self.iops= kargs.get('iops',0)
      self.ioRequests= int(kargs.get('ioRequests',0))
      self.backupStorageGbMonth = int(kargs.get('backupStorageGbMonth',0))

      self.validate()

      if self.engine in (consts.SCRIPT_RDS_DATABASE_ENGINE_AURORA_MYSQL, consts.SCRIPT_RDS_DATABASE_ENGINE_AURORA_MYSQL):
          self.storageType = consts.SCRIPT_RDS_STORAGE_TYPE_AURORA
      self.volumeType = self.calculate_volume_type()



    def calculate_volume_type(self):
      #TODO:add condition for Aurora
      if self.storageType in consts.RDS_VOLUME_TYPES_MAP:
        return consts.RDS_VOLUME_TYPES_MAP[self.storageType]

    def validate(self):
      #TODO: add validations for data transfer
      #TODO: add validations for different combinations of engine, edition and license
      validation_ok = True
      validation_message = ""
      valid_engine = True

      if not isinstance(self.multiAz, bool):
        validation_message = "\n you have specified multiAz as [{}], it has to be boolean".format(self.multiAz)
      if self.dbInstanceClass and self.dbInstanceClass not in consts.SUPPORTED_RDS_INSTANCE_CLASSES:
        validation_message = "\n" + "db-instance-class must be one of the following values:"+str(consts.SUPPORTED_RDS_INSTANCE_CLASSES)
      if self.region not in consts.SUPPORTED_REGIONS:
        validation_message += "\n" + "region must be one of the following values:"+str(consts.SUPPORTED_REGIONS)
      if self.engine and self.engine not in consts.RDS_SUPPORTED_DB_ENGINES:
        validation_message += "\n" + "engine must be one of the following values:"+str(consts.RDS_SUPPORTED_DB_ENGINES)
        valid_engine  = False
      if valid_engine and self.engine in (consts.SCRIPT_RDS_DATABASE_ENGINE_MYSQL,consts.SCRIPT_RDS_DATABASE_ENGINE_POSTGRESQL,
                                              consts.SCRIPT_RDS_DATABASE_ENGINE_AURORA_MYSQL, consts.SCRIPT_RDS_DATABASE_ENGINE_AURORA_POSTGRESQL):
        if self.licenseModel not in (consts.RDS_SUPPORTED_LICENSE_MODELS):
          validation_message += "\n" + "you have specified license model [{}] - license-model must be one of the following values:{}".format(self.licenseModel, consts.RDS_SUPPORTED_LICENSE_MODELS)
      if self.engine in (consts.SCRIPT_RDS_DATABASE_ENGINE_AURORA_MYSQL, consts.SCRIPT_RDS_DATABASE_ENGINE_AURORA_POSTGRESQL):
          if self.storageType in (consts.SCRIPT_RDS_STORAGE_TYPE_STANDARD, consts.SCRIPT_RDS_STORAGE_TYPE_GP2, consts.SCRIPT_RDS_STORAGE_TYPE_IO1):
              validation_message += "\nyou have specified {} storage type, which is invalid for DB engine {}".format(self.storageType, self.engine)
      if self.storageType:
        if self.storageType not in consts.SUPPORTED_RDS_STORAGE_TYPES:
          validation_message += "\n" + "storage-type must be one of the following values:"+str(consts.SUPPORTED_RDS_STORAGE_TYPES)
        if self.storageType == consts.SCRIPT_RDS_STORAGE_TYPE_IO1 and not self.iops:
          validation_message += "\n" + "you must specify an iops value for storage type io1"
        if self.storageType == consts.SCRIPT_RDS_STORAGE_TYPE_IO1 and self.storageGbMonth < 100 :
          validation_message += "\nyou have specified {}GB of storage. You must specify at least 100GB of storage for io1".format(self.storageGbMonth)

      if self.termType not in consts.SUPPORTED_TERM_TYPES:
          validation_message += "term-type is "+self.termType+", must be one of the following values:[{}]".format(consts.SUPPORTED_TERM_TYPES)

      #TODO: move to a common place for all reserved pricing (EC2, RDS, etc.)
      if self.termType == consts.SCRIPT_TERM_TYPE_RESERVED:
          if not self.offeringClass:
              validation_message += "offering-class must be specified for Reserved instances\n"
          if self.offeringClass and self.offeringClass not in (consts.SUPPORTED_EC2_OFFERING_CLASSES):
              validation_message += "offering-class is "+self.offeringClass+", must be one of the following values:"+str(consts.SUPPORTED_EC2_OFFERING_CLASSES)
          if not self.offeringType:
              validation_message += "offering-type must be specified\n"
          if self.offeringType and self.offeringType not in (consts.EC2_SUPPORTED_PURCHASE_OPTIONS):
              validation_message += "offering-type is "+self.offeringType+", must be one of the following values:"+str(consts.EC2_SUPPORTED_PURCHASE_OPTIONS)
          if self.offeringType == consts.SCRIPT_EC2_PURCHASE_OPTION_ALL_UPFRONT and self.instanceHours:
              validation_message += "instance-hours cannot be set if term-type=reserved and offering-type=all-upfront\n"
          if self.offeringType == consts.SCRIPT_EC2_PURCHASE_OPTION_ALL_UPFRONT and not self.instanceCount:
              validation_message += "instance-count is mandatory if term-type=reserved and offering-type=all-upfront\n"
          if not self.years:
              validation_message += "years cannot be empty for Reserved instances"


      if validation_message:
          log.error("{}".format(validation_message))
          raise ValidationError(validation_message)

      return




class LambdaPriceDimension():
    def __init__(self,**kargs):
        self.region = kargs.get('region','')
        self.termType = consts.SCRIPT_TERM_TYPE_ON_DEMAND
        self.requestCount = kargs.get('requestCount',0)
        self.avgDurationMs = kargs.get('avgDurationMs',0)
        self.memoryMb = kargs.get('memoryMb',0)
        self.dataTransferOutInternetGb = kargs.get('dataTransferOutInternetGb',0)
        self.dataTransferOutIntraRegionGb = kargs.get('dataTransferOutIntraRegionGb')
        self.dataTransferOutInterRegionGb = kargs.get('dataTransferOutInterRegionGb',0)
        self.toRegion = kargs.get('toRegion','')
        self.validate()
        self.GBs = self.requestCount * (float(self.avgDurationMs) / 1000) * (float(self.memoryMb) / 1024)


    def validate(self):
        validation_message = ""
        if not self.region:
            validation_message += "Region must be specified\n"
        if self.region not in consts.SUPPORTED_REGIONS:
            validation_message += "Region is "+self.region+" ,must be one of the following:"+str(consts.SUPPORTED_REGIONS)
        if self.requestCount and self.avgDurationMs == 0:
            validation_message += "Cannot have value for requestCount and avgDurationMs=0\n"
        if self.requestCount and self.memoryMb== 0:
            validation_message += "Cannot have value for requestCount and memoryMb=0\n"
        if self.requestCount == 0 and (self.avgDurationMs > 0 or self.memoryMb > 0):
            validation_message += "Cannot have value for average duration or memory if requestCount is zero\n"
        if self.dataTransferOutInterRegionGb > 0 and not self.toRegion:
            validation_message += "Must specify a to-region if you specify data-transfer-out-interregion-gb\n"

        if validation_message:
            log.error("{}".format(validation_message))
            raise ValidationError(validation_message)

        return



class DynamoDBPriceDimension():
    def __init__(self,**kargs):
        self.region = kargs.get('region','')
        self.termType = consts.SCRIPT_TERM_TYPE_ON_DEMAND
        self.readCapacityUnitHours = kargs.get('readCapacityUnitHours',0)
        self.writeCapacityUnitHours = kargs.get('writeCapacityUnitHours',0)
        self.requestCount = kargs.get('requestCount',0)#used for reads to DDB Streams
        self.dataTransferOutGb = kargs.get('dataTransferOutGb',0)
        """
        self.dataTransferOutInterRegionGb = kargs.get('dataTransferOutInterRegionGb',0)
        self.toRegion = kargs.get('toRegion','')
        """

        self.validate()


    def validate(self):
        validation_message = ""
        if not self.region:
            validation_message += "Region must be specified\n"
        if self.region not in consts.SUPPORTED_REGIONS:
            validation_message += "Region is "+self.region+", must be one of the following:"+str(consts.SUPPORTED_REGIONS)
        if self.readCapacityUnitHours == 0:
            validation_message += "readCapacityUnitHours cannot be 0\n"
        if self.writeCapacityUnitHours == 0:
            validation_message += "writeCapacityUnitHours cannot be 0\n"

        if validation_message:
            print("Error: [{}]".format(validation_message))
            raise ValidationError(validation_message)

        return


"""
Please note the following - from https://aws.amazon.com/kinesis/streams/pricing/:
* Getting records from Amazon Kinesis stream is free.
* Data transfer is free. AWS does not charge for data transfer from your data producers to Amazon Kinesis Streams, or from Amazon Kinesis Streams to your Amazon Kinesis Applications.
"""

class KinesisPriceDimension():
    def __init__(self,**kargs):
        self.region = kargs.get('region','')
        self.termType = consts.SCRIPT_TERM_TYPE_ON_DEMAND
        self.shardHours = 0
        self.shardHours = int(kargs.get('shardHours',0))
        self.putPayloadUnits = int(kargs.get('putPayloadUnits',0))
        self.extendedDataRetentionHours = int(kargs.get('extendedDataRetentionHours',0))
        self.validate()

    def validate(self):
        validation_message = ""
        if not self.region:
            validation_message += "Region must be specified\n"
        if self.region not in consts.SUPPORTED_REGIONS:
            validation_message += "region is "+self.region+", must be one of the following values:"+str(consts.SUPPORTED_REGIONS)
        if self.shardHours == 0:
            validation_message += "shardHours cannot be 0\n"

        if validation_message:
            print("Error: [{}]".format(validation_message))
            raise ValidationError(validation_message)

        return


"""
This object represents the total price calculation.
It includes an array of PricingRecord objects, which are a breakdown of how the price is calculated
"""
class PricingResult():
    def __init__(self, awsPriceListApiVersion, region, total_cost, pricing_records):
        total_cost = round(total_cost,2)
        self.version = consts.AWS_PRICE_CALCULATOR_VERSION
        self.awsPriceListApiVersion = awsPriceListApiVersion
        self.region = region
        self.totalCost = round(total_cost,2)
        self.currency = consts.DEFAULT_CURRENCY
        self.pricingRecords = pricing_records

        #TODO: populate this object
        self.priceDimensions = {}

class PricingRecord():
    def __init__(self, service, amt, desc, pricePerUnit, usgUnits, rateCode):
        usgUnits = round(float(usgUnits),2)
        amt = round(amt,2)
        self.service = service
        self.amount = amt
        self.description = desc
        self.pricePerUnit = pricePerUnit
        self.usageUnits = int(usgUnits)
        self.rateCode = rateCode


"""
This class is a container for generic price comparisons, with different values for a single parameter.
For example, comparing a specific price calculation for different regions, or EC2 instance types, or OS
"""
class PriceComparison():
    def __init__(self, awsPriceListApiVersion, service, sortCriteria):
        self.version = "v1.0"
        self.awsPriceListApiVersion = awsPriceListApiVersion
        self.service = service
        self.sortCriteria = sortCriteria
        self.currency = consts.DEFAULT_CURRENCY
        self.pricingScenarios = []

class PricingScenario():
    def __init__(self, index, id, priceDimensions, priceCalculation, totalCost, sortCriteria):
        self.index = index
        self.id = id
        self.displayName = self.getDisplayName(sortCriteria)
        self.priceDimensions = priceDimensions

        #Remove redundant information from priceCalculation object.
        #This information is already present in PriceComparison or PricingScenario objects
        priceCalculation.pop('awsPriceListApiVersion','')
        priceCalculation.pop('totalCost','')
        priceCalculation.pop('service','')
        priceCalculation.pop('currency','')


        self.priceCalculation = priceCalculation
        self.totalCost = totalCost
        self.deltaPrevious = 0 #how more expensive is this item, compared to cheapest option - in $
        self.deltaCheapest = 0 #how more expensive is this item, compared to cheapest option - in %
        self.pctToPrevious = 0 #how more expensive is this item, compared to next lower option - in $
        self.pctToCheapest = 0 #how more expensive is this item, compared to next lower option - in %
        self.totalCost = totalCost

    def getDisplayName(self, sortCriteria):
        result =  ''
        if sortCriteria == consts.SORT_CRITERIA_REGION:
            result = consts.REGION_REPORT_MAP.get(self.id,'N/A')

        #TODO: update for all supported sortCriteria options
        else:
            result = self.id

        return result


"""
This class is a container for price calculations between different term types, such as Demand vs. Reserved
"""
class TermPricingAnalysis():
    def __init__(self, awsPriceListApiVersion, region, service, years):
        self.version = "v1.0"
        self.awsPriceListApiVersion = awsPriceListApiVersion
        self.region = region
        self.service = service
        self.currency = consts.DEFAULT_CURRENCY
        self.years = years
        self.pricingScenarios = []

    def get_pricing_scenario(self, termType, offerClass, offerType, years):
        #print ("get_pricing_scenario - looking for termType:[{}] - offerClass:[{}] - offerType:[{}] - years:[{}]".format())
        for p in self.pricingScenarios:
            print ("get_pricing_scenario - looking for termType:[{}] - offerClass:[{}] - offerType:[{}] - years:[{}] in priceDimensions: [{}]".format(termType, offerClass, offerType, years, p['priceDimensions']))
            if p['priceDimensions']['termType']==termType \
                    and p['priceDimensions'].get('offeringClass',consts.SCRIPT_EC2_OFFERING_CLASS_STANDARD)==offerClass \
                    and p['priceDimensions'].get('offeringType','')==offerType and str(p['priceDimensions']['years'])==str(years):
                return p
            if p['priceDimensions']['termType']==termType and termType == consts.SCRIPT_TERM_TYPE_ON_DEMAND \
                    and str(p['priceDimensions']['years'])==str(years):
                return p

        return False

    def calculate_months_to_recover(self):
        updatedPricingScenarios = []

        for s in self.pricingScenarios:
            accumamt = 0
            month = 1
            while month <= int(self.years)*12:
                if month == 1:
                    if s['id'] == 'reserved-partial-upfront-{}yr'.format(self.years):
                        accumamt = self.getUpfrontFee(self.get_pricing_scenario(consts.SCRIPT_TERM_TYPE_RESERVED,
                                                                                consts.SCRIPT_EC2_OFFERING_CLASS_STANDARD,
                                                                                consts.SCRIPT_EC2_PURCHASE_OPTION_PARTIAL_UPFRONT, str(self.years)))
                    if s['id'] == 'reserved-all-upfront-{}yr'.format(self.years):
                        accumamt = self.getUpfrontFee(self.get_pricing_scenario(consts.SCRIPT_TERM_TYPE_RESERVED,
                                                                             consts.SCRIPT_EC2_OFFERING_CLASS_STANDARD,
                                                                             consts.SCRIPT_EC2_PURCHASE_OPTION_ALL_UPFRONT, str(self.years)))


                if s['id'] == 'reserved-partial-upfront-{}yr'.format(self.years): accumamt += self.getMonthlyCost(self.get_pricing_scenario(consts.SCRIPT_TERM_TYPE_RESERVED, consts.SCRIPT_EC2_OFFERING_CLASS_STANDARD, consts.SCRIPT_EC2_PURCHASE_OPTION_PARTIAL_UPFRONT, self.years))
                if s['id'] == 'reserved-no-upfront-{}yr'.format(self.years): accumamt += self.getMonthlyCost(self.get_pricing_scenario(consts.SCRIPT_TERM_TYPE_RESERVED, consts.SCRIPT_EC2_OFFERING_CLASS_STANDARD, consts.SCRIPT_EC2_PURCHASE_OPTION_NO_UPFRONT, self.years))

                if ((s['onDemandTotalCost']/(int(self.years)*12))*month) >= accumamt:
                    break
                month += 1

            s['monthsToRecover'] = month
            updatedPricingScenarios.append(s)

        self.pricingScenarios = updatedPricingScenarios


    def get_csv_data(self):
        #TODO: validate that years is either 1 or 3

        def get_csv_dict():
            result = {}
            for k in get_sorted_keys():
                result[k[1]]=0
            return result

        def get_sorted_keys():
            #TODO: add to constants
            #TODO: update order in which scenarios get displayed
            return sorted(((1,'month'),(2,'on-demand-{}yr'.format(self.years)),(3,'reserved-all-upfront-{}yr'.format(self.years)),
                           (4,'reserved-partial-upfront-{}yr'.format(self.years)),(4,'reserved-no-upfront-{}yr'.format(self.years))))

        def get_sorted_key_separator(k):
            result = ','
            sortedkeys = get_sorted_keys()
            if k == sortedkeys[len(sortedkeys)-1]:result = '' #don't add a comma at the end of the line
            return result

        month = 1

        #TODO: see if this block can be removed
        for s in self.pricingScenarios:
            if s['id'] == "on-demand-{}yr".format(self.years): onDemand = s['pricingRecords']
            if s['id'] == "reserved-no-upfront-{}yr".format(self.years): reserved1YrNoUpfront = s['pricingRecords']
            if s['id'] == "reserved-all-upfront-{}yr".format(self.years): reserved1YrAllUpfrontAccum = s['totalCost']
            for p in s['pricingRecords']:
                if 'upfront' in p['description'].lower():
                    if s['id'] == "reserved-partial-upfront-{}yr".format(self.years): reserved1YrPartialUpfront = p['amount']
                    if s['id'] == "reserved-all-upfront-{}yr".format(self.years): reserved1YrAllUpfront = p['amount']
                else: reserved1YrPartialUpfrontApplied = p['amount']

        accumDict = get_csv_dict()

        csvdata = ""
        sortedkeys = get_sorted_keys()
        while month <= int(self.years) * 12:
            accumDict['month']=month
            if month == 1:
              accumDict['reserved-partial-upfront-{}yr'.format(self.years)] = self.getUpfrontFee(self.get_pricing_scenario(consts.SCRIPT_TERM_TYPE_RESERVED, consts.SCRIPT_EC2_OFFERING_CLASS_STANDARD, consts.SCRIPT_EC2_PURCHASE_OPTION_PARTIAL_UPFRONT, str(self.years)))

            accumDict['reserved-all-upfront-{}yr'.format(self.years)] = self.getUpfrontFee(self.get_pricing_scenario(consts.SCRIPT_TERM_TYPE_RESERVED, consts.SCRIPT_EC2_OFFERING_CLASS_STANDARD, consts.SCRIPT_EC2_PURCHASE_OPTION_ALL_UPFRONT, str(self.years)))
            accumDict['reserved-partial-upfront-{}yr'.format(self.years)] += self.getMonthlyCost(self.get_pricing_scenario(consts.SCRIPT_TERM_TYPE_RESERVED, consts.SCRIPT_EC2_OFFERING_CLASS_STANDARD, consts.SCRIPT_EC2_PURCHASE_OPTION_PARTIAL_UPFRONT, str(self.years)))
            accumDict['on-demand-{}yr'.format(self.years)] += self.getMonthlyCost(self.get_pricing_scenario(consts.SCRIPT_TERM_TYPE_ON_DEMAND, consts.SCRIPT_EC2_OFFERING_CLASS_STANDARD, consts.SCRIPT_EC2_PURCHASE_OPTION_PARTIAL_UPFRONT, str(self.years)))
            accumDict['reserved-no-upfront-{}yr'.format(self.years)] += self.getMonthlyCost(self.get_pricing_scenario(consts.SCRIPT_TERM_TYPE_RESERVED, consts.SCRIPT_EC2_OFFERING_CLASS_STANDARD, consts.SCRIPT_EC2_PURCHASE_OPTION_NO_UPFRONT, str(self.years)))

            for k in sortedkeys:
                amt = 0
                if k[1] == 'month': amt = accumDict[k[1]]
                else: amt = round(accumDict[k[1]],2)
                csvdata += "{}{}".format(amt,get_sorted_key_separator(k))

            csvdata += "\n"
            month += 1

        csvheaders = ""
        for k in sortedkeys: csvheaders += k[1]+get_sorted_key_separator(k)
        csvheaders += "\n"
        self.csvData = csvheaders + csvdata
        return


    def getUpfrontFee(self, pricingScenarioDict):
        result = 0
        if pricingScenarioDict:
            for p in pricingScenarioDict['pricingRecords']:
                if pricingScenarioDict['priceDimensions'].get('offeringType','') in (consts.SCRIPT_EC2_PURCHASE_OPTION_ALL_UPFRONT, consts.SCRIPT_EC2_PURCHASE_OPTION_PARTIAL_UPFRONT) \
                    and 'upfront' in p['description'].lower():
                    result = p['amount']
                    break
        return result

    def getMonthlyCost(self, pricingScenarioDict):
        result = 0
        if pricingScenarioDict:
            for p in pricingScenarioDict['pricingRecords']:
                if pricingScenarioDict['priceDimensions'].get('offeringType','') != consts.SCRIPT_EC2_PURCHASE_OPTION_ALL_UPFRONT \
                    and 'upfront' not in p['description'].lower():
                    return p['amount'] / (12 * int(pricingScenarioDict['priceDimensions']['years']))
        else: return result


class TermPricingScenario():
    def __init__(self, id, priceDimensions, pricingRecords, totalCost, onDemandTotalCost):
        self.index = None
        self.id = id
        self.priceDimensions = priceDimensions
        self.pricingRecords = pricingRecords
        self.totalCost = totalCost
        self.deltaPrevious = 0 #how more expensive is this item, compared to cheapest option - in $
        self.deltaCheapest = 0 #how more expensive is this item, compared to cheapest option - in %
        self.pctToPrevious = 0 #how more expensive is this item, compared to next lower option - in $
        self.pctToCheapest = 0 #how more expensive is this item, compared to next lower option - in %
        self.onDemandTotalCost = onDemandTotalCost
        self.savingsPctvsOnDemand = 0
        self.totalSavingsvsOnDemand = 0
        self.monthsToRecover = 0
        #TODO: implement onDemandMonthsToSavings
        #TODO: implement as a subclass of PricingScenario

    def calculateOnDemandSavings(self):
        #TODO: confirm if Partial Upfront is 1 upfront + 12 payments and if the initial payment is applied on month 1
        if self.onDemandTotalCost:
            self.savingsPctvsOnDemand  = math.fabs(round((100 * (self.totalCost - self.onDemandTotalCost) / self.onDemandTotalCost),2))
        if self.priceDimensions['termType'] == consts.SCRIPT_TERM_TYPE_ON_DEMAND:
            self.totalSavingsvsOnDemand = 0
        else:
            self.totalSavingsvsOnDemand = round((self.onDemandTotalCost - self.totalCost),2)





