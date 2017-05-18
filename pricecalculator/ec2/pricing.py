
import json
import logging
from ..common import consts, phelper
from ..common.data import PricingResult
import tinydb



log = logging.getLogger()


def calculate(pdim):

  ts = phelper.Timestamp()
  ts.start('totalCalculation')

  log.info("Calculating EC2 pricing with the following inputs: {}".format(str(pdim.__dict__)))
  #print("Calculating EC2 pricing with the following inputs: {}".format(str(pdim.__dict__)))

  ts.start('tinyDbLoad')
  dbs, indexMetadata = phelper.loadDBs(consts.SERVICE_EC2, phelper.get_partition_keys(pdim.region))
  ts.finish('tinyDbLoad')
  print "Time to load DB files: [{}]".format(ts.elapsed('tinyDbLoad'))

  cost = 0
  pricing_records = []

  awsPriceListApiVersion = indexMetadata['Version']

  priceQuery = tinydb.Query()

  #TODO: Move common operations to a common module, and leave only EC2-specific operations in ec2/pricing.py
  #Compute Instance
  if pdim.instanceHours:
    computeDb = dbs[phelper.create_file_key(consts.REGION_MAP[pdim.region], consts.TERM_TYPE_MAP[pdim.termType], consts.PRODUCT_FAMILY_COMPUTE_INSTANCE)]
    ts.start('tinyDbSearchComputeFile')
    purchaseOption = ''
    if pdim.purchaseOption in consts.EC2_PURCHASE_OPTION_MAP:
      purchaseOption = consts.EC2_PURCHASE_OPTION_MAP[pdim.purchaseOption]
    query = ((priceQuery['Instance Type'] == pdim.instanceType) &
            (priceQuery['Operating System'] == consts.EC2_OPERATING_SYSTEMS_MAP[pdim.operatingSystem]) &
            (priceQuery['Tenancy'] == consts.EC2_TENANCY_SHARED) &
            (priceQuery['Pre Installed S/W'] == pdim.preInstalledSoftware) &
            (priceQuery['License Model'] == consts.EC2_LICENSE_MODEL_MAP[pdim.licenseModel]) &
            (priceQuery['OfferingClass'] == pdim.offeringClass) &
            (priceQuery['PurchaseOption'] == purchaseOption ))

    pricing_records, cost = phelper.calculate_price(consts.SERVICE_EC2, computeDb, query, pdim.instanceHours, pricing_records, cost)
    print "Time to search compute:[{}]".format(ts.finish('tinyDbSearchComputeFile'))

  #Data Transfer
  dataTransferDb = dbs[phelper.create_file_key(consts.REGION_MAP[pdim.region], consts.TERM_TYPE_MAP[pdim.termType], consts.PRODUCT_FAMILY_DATA_TRANSFER)]

  #Out to the Internet
  if pdim.dataTransferOutInternetGb:
    ts.start('searchDataTransfer')
    query = ((priceQuery['To Location'] == 'External') & (priceQuery['Transfer Type'] == 'AWS Outbound'))
    pricing_records, cost = phelper.calculate_price(consts.SERVICE_EC2, dataTransferDb, query, pdim.dataTransferOutInternetGb, pricing_records, cost)
    print "Time to search EC2 data transfer Out: [{}]".format(ts.finish('searchDataTransfer'))

  #Intra-regional data transfer - in/out/between EC2 AZs or using EIPs or ELB
  if pdim.dataTransferOutIntraRegionGb:
    query = ((priceQuery['Transfer Type'] == 'IntraRegion'))
    pricing_records, cost = phelper.calculate_price(consts.SERVICE_EC2, dataTransferDb, query, pdim.dataTransferOutIntraRegionGb, pricing_records, cost)

  #Inter-regional data transfer - out to other AWS regions
  if pdim.dataTransferOutInterRegionGb:
    query = ((priceQuery['Transfer Type'] == 'InterRegion Outbound') & (priceQuery['To Location'] == consts.REGION_MAP[pdim.toRegion]))
    pricing_records, cost = phelper.calculate_price(consts.SERVICE_EC2, dataTransferDb, query, pdim.dataTransferOutInterRegionGb, pricing_records, cost)

  #EBS Storage
  if pdim.ebsStorageGbMonth:
    storageDb = dbs[phelper.create_file_key(consts.REGION_MAP[pdim.region], consts.TERM_TYPE_MAP[pdim.termType], consts.PRODUCT_FAMILY_STORAGE)]
    query = ((priceQuery['Volume Type'] == pdim.volumeType))
    pricing_records, cost = phelper.calculate_price(consts.SERVICE_EBS, storageDb, query, pdim.ebsStorageGbMonth, pricing_records, cost)


  #System Operation (pIOPS)
  if pdim.volumeType == consts.EBS_VOLUME_TYPE_PIOPS and pdim.pIops:
    storageDb = dbs[phelper.create_file_key(consts.REGION_MAP[pdim.region], consts.TERM_TYPE_MAP[pdim.termType], consts.PRODUCT_FAMILY_SYSTEM_OPERATION)]
    query = ((priceQuery['Group'] == 'EBS IOPS'))
    pricing_records, cost = phelper.calculate_price(consts.SERVICE_EBS, storageDb, query, pdim.pIops, pricing_records, cost)

  #Snapshot Storage
  if pdim.ebsSnapshotGbMonth:
    snapshotDb = dbs[phelper.create_file_key(consts.REGION_MAP[pdim.region], consts.TERM_TYPE_MAP[pdim.termType], consts.PRODUCT_FAMILY_SNAPSHOT)]
    query = ((priceQuery['usageType'] == consts.REGION_PREFIX_MAP[pdim.region]+'EBS:SnapshotUsage'))#EBS:SnapshotUsage comes with a prefix in the PriceList API file (i.e. EU-EBS:SnapshotUsage)
    pricing_records, cost = phelper.calculate_price(consts.SERVICE_EBS, snapshotDb, query, pdim.ebsSnapshotGbMonth, pricing_records, cost)

  #Load Balancer
  if pdim.elbHours:
    elbDb = dbs[phelper.create_file_key(consts.REGION_MAP[pdim.region], consts.TERM_TYPE_MAP[pdim.termType], consts.PRODUCT_FAMILY_LOAD_BALANCER)]
    #TODO:Add support for LoadBalancing:Application
    query = ((priceQuery['usageType'] == consts.REGION_PREFIX_MAP[pdim.region]+'LoadBalancerUsage') & (priceQuery['operation'] == 'LoadBalancing'))
    pricing_records, cost = phelper.calculate_price(consts.SERVICE_ELB, elbDb, query, pdim.elbHours, pricing_records, cost)

  if pdim.elbDataProcessedGb:
    elbDb = dbs[phelper.create_file_key(consts.REGION_MAP[pdim.region], consts.TERM_TYPE_MAP[pdim.termType], consts.PRODUCT_FAMILY_LOAD_BALANCER)]
    query = ((priceQuery['usageType'] == consts.REGION_PREFIX_MAP[pdim.region]+'DataProcessing-Bytes') & (priceQuery['operation'] == 'LoadBalancing'))
    pricing_records, cost = phelper.calculate_price(consts.SERVICE_ELB, elbDb, query, pdim.elbDataProcessedGb, pricing_records, cost)


  #EIP
  #Dedicated Host
  #NAT Gateway
  #Fee


  pricing_result = PricingResult(awsPriceListApiVersion, pdim.region, cost, pricing_records)
  log.debug(json.dumps(vars(pricing_result),sort_keys=False,indent=4))

  print "Total time to compute: [{}]".format(ts.finish('totalCalculation'))
  return pricing_result.__dict__


