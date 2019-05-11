#!/usr/bin/python
import sys, os, json, time
import argparse
import traceback
import boto3
from botocore.exceptions import ClientError
import math
sys.path.insert(0, os.path.abspath('..'))
sys.path.insert(0, os.path.abspath('../vendored'))

import numpy

import awspricecalculator.awslambda.pricing as lambdapricing
import awspricecalculator.common.models as data
import awspricecalculator.common.consts as consts
import awspricecalculator.common.errors as errors

logsclient = boto3.client('logs')
lambdaclient = boto3.client('lambda')


MONTHLY = "MONTHLY"
MS_MAP = {MONTHLY:(3.6E6)*720}




def main(argv):

  region = os.environ['AWS_DEFAULT_REGION']

  parser = argparse.ArgumentParser()
  parser.add_argument('--function', help='', required=True)
  parser.add_argument('--minutes', help='', required=True)

  if len(sys.argv) == 1:
    parser.print_help()
    sys.exit(1)
  args = parser.parse_args()

  function = ''
  minutes = 0 #in minutes


  if args.function: function = args.function
  if args.minutes: minutes = int(args.minutes)

  try:
    validate(function, minutes)
  except errors.ValidationError as error:
    print(error.message)
    sys.exit(1)

  mem_used_array = []
  duration_array = []
  prov_mem_size = 0
  firstEventTs = 0
  lastEventTs = 0
  ts_format = "%Y-%m-%d %H:%M:%S UTC"
  log_group_name = '/aws/lambda/'+function

  try:
    i = 0
    windowStartTime = (int(time.time()) - minutes * 60) * 1000
    firstEventTs = windowStartTime #temporary value, it will be updated once (if) we get results from the CW Logs get_log_events API
    lastEventTs = int(time.time() * 1000) #this will also be updated once (if) we get results from the CW Logs get_log_events API
    nextLogstreamToken = True
    logstreamsargs = {'logGroupName':log_group_name, 'orderBy':'LastEventTime', 'descending':True}
    while nextLogstreamToken:
        logstreams = logsclient.describe_log_streams(**logstreamsargs)
        """
        Read through CW Logs entries and extract information from them.
        We're interested in entries that look like this:
           REPORT RequestId: 7686bf2c-2f79-11e7-b693-97868a5db36b	Duration: 5793.53 ms	Billed Duration: 5800 ms 	Memory Size: 448 MB	Max Memory Used: 24 MB
        """

        if 'logStreams' in logstreams:
            print("Number of logstreams found:[{}]".format(len(logstreams['logStreams'])))

            nextLogstreamToken = logstreams.get('nextToken',False)
            if nextLogstreamToken: logstreamsargs['nextToken']=nextLogstreamToken
            else:logstreamsargs.pop('nextToken',False)

            #Go through all logstreams in descending order
            for ls in logstreams['logStreams']:
                nextEventsForwardToken = True
                logeventsargs = {'logGroupName':log_group_name, 'logStreamName':ls['logStreamName'],
                                 'startFromHead':True, 'startTime':windowStartTime}
                while nextEventsForwardToken:
                    logevents = logsclient.get_log_events(**logeventsargs)
                    if 'events' in logevents:
                        if len(logevents['events']):
                            print ("\nEvents for logGroup:[{}] - logstream:[{}] - nextForwardToken:[{}]".format(log_group_name, ls['logStreamName'],nextEventsForwardToken))
                            for e in logevents['events']:
                                #Extract lambda execution duration and memory utilization from "REPORT" log events
                                if 'REPORT RequestId:' in e['message']:
                                    mem_used = e['message'].split('Max Memory Used: ')[1].split()[0]
                                    mem_used_array.append(int(mem_used))
                                    duration = e['message'].split('Billed Duration: ')[1].split()[0]
                                    duration_array.append(int(duration))
                                    if i == 0:
                                        prov_mem_size = int(e['message'].split('Memory Size: ')[1].split()[0])
                                        firstEventTs = e['timestamp']
                                        lastEventTs = e['timestamp']
                                    else:
                                        if e['timestamp'] < firstEventTs: firstEventTs = e['timestamp']
                                        if e['timestamp'] > lastEventTs: lastEventTs = e['timestamp']
                                    print ("mem_used:[{}] - mem_size:[{}] - timestampMs:[{}] -  timestamp:[{}]".format(mem_used,prov_mem_size, e['timestamp'], time.strftime(ts_format, time.gmtime(e['timestamp']/1000))))
                                    print e['message']
                                    i += 1
                        else: break

                    nextEventsForwardToken = logevents.get('nextForwardToken',False)
                    if nextEventsForwardToken: logeventsargs['nextToken']=nextEventsForwardToken
                    else: logeventsargs.pop('nextToken',False)



    #Once we've iterated through all log streams and log events, calculate averages, cost and optimization scenarios
    avg_used_mem = 0
    avg_duration_ms = 0
    p90_duration_ms = 0
    p99_duration_ms = 0
    p100_duration_ms = 0

    if mem_used_array: avg_used_mem = math.ceil(numpy.average(mem_used_array))
    if duration_array:
        avg_duration_ms = round(math.ceil(numpy.average(duration_array)),0)
        p90_duration_ms = round(math.ceil(numpy.percentile(duration_array, 90)),0)
        p99_duration_ms = round(math.ceil(numpy.percentile(duration_array, 99)),0)
        p100_duration_ms = round(math.ceil(numpy.percentile(duration_array, 100)),0)
    base_usage = LambdaSampleUsage(region, i, avg_duration_ms, avg_used_mem, prov_mem_size, firstEventTs, lastEventTs, MONTHLY)
    memoptims= []
    durationoptims = []
    current_cost = 0

    for m in get_lower_possible_memory_ranges(avg_used_mem, prov_mem_size):
        #TODO: add target memory % utilization (i.e. I want to use 60% of memory and see how much that'll save me)
        memoptims.append(LambdaUtilScenario(base_usage, base_usage.avgDurationMs, m).__dict__)


    for d in get_lower_possible_durations(avg_duration_ms, 100):
        durationoptims.append(LambdaUtilScenario(base_usage, d, base_usage.memSizeMb).__dict__)


    optim_info = {"sampleUsage":base_usage.__dict__,
                  "memoryOptimizationScenarios":memoptims,
                  "durationOptimizationScenarios":durationoptims
                  }
    #print(json.dumps(optim_info,sort_keys=False,indent=4))

    print ("avg_duration_ms:[{}] avg_used_mem:[{}] prov_mem_size:[{}] records:[{}]".format(avg_duration_ms, avg_used_mem,prov_mem_size,i))
    print ("p90_duration_ms:[{}] p99_duration_ms:[{}] p100_duration_ms:[{}]".format(p90_duration_ms, p99_duration_ms, p100_duration_ms))

    print ("------------------------------------------------------------------------------------")
    print ("OPTIMIZATION SUMMARY\n")
    print ("**Data sample used for calculation:**")
    print ("CloudWatch Log Group: [{}]\n" \
          "First Event time:[{}]\n" \
          "Last Event time:[{}]\n" \
          "Number of executions:[{}]\n" \
          "Average executions per second:[{}]".\
        format(log_group_name,
               time.strftime(ts_format, time.gmtime(base_usage.startTs/1000)),
               time.strftime(ts_format, time.gmtime(base_usage.endTs/1000)),
               base_usage.requestCount, base_usage.avgTps))
    print ("\n**Usage for Lambda function [{}] in the sample period is the following:**".format(function))
    print ("Average duration per Lambda execution: {}ms\n" \
          "Average consumed memory per execution: {}MB\n" \
          "Configured memory in your Lambda function: {}MB\n" \
          "Memory utilization (used/allocated): {}%\n" \
          "Total projected cost: ${}USD - {}".\
          format(base_usage.avgDurationMs, base_usage.avgMemUsedMb,base_usage.memSizeMb,
                base_usage.memUsedPct,base_usage.projectedCost, base_usage.projectedPeriod))

    if memoptims:
        print ("\nThe following Lambda memory configurations could save you money (assuming constant execution time)")
        labels = ['memSizeMb', 'memUsedPct', 'cost', 'timePeriod', 'savingsAmt']
        print ("\n"+ResultsTable(memoptims,labels).dict2md())
    if durationoptims:
        print ("\n\nCan you make your function execute faster? The following Lambda execution durations will save you money (assuming memory allocation remains constant):")
        labels = ['durationMs', 'cost', 'timePeriod', 'savingsAmt']
        print ("\n"+ResultsTable(durationoptims,labels).dict2md())
    print ("------------------------------------------------------------------------------------")



  except Exception as e:
    traceback.print_exc()
    print("Exception message:["+str(e.message)+"]")


"""
Get the possible Lambda memory configurations values that would:
- Be lower than the current provisioned value (thus, cheaper)
- Are greater than the current average used memory (therefore won't result in memory errors)
"""

def get_lower_possible_memory_ranges(usedMem, provMem):
    result = []
    for m in consts.LAMBDA_MEM_SIZES:
        if usedMem < float(m) and m < provMem:
            result.append(m)
    return result


"""
Get the possible Lambda execution values that would:
- Be lower than the current average duration (thus, cheaper)
- Are greater than a lower limit set by the user of the script (there's only so much one can do to make a function run faster)
"""
def get_lower_possible_durations(usedDurationMs, lowestDuration):
    result = []
    initBilledDurationMs = math.floor(usedDurationMs / 100) * 100
    d = int(initBilledDurationMs)
    while d >= lowestDuration:
            result.append(d)
            d -= 100
    return result



#TODO:Move to a different file
#This class models the usage for a Lambda function within a time window defined by startTs and endTs
class LambdaSampleUsage():
    def __init__(self, region, requestCount, avgDurationMs, avgMemUsedMb, memSizeMb, startTs, endTs, projectedPeriod):

        self.region = region

        self.requestCount = 0
        if requestCount: self.requestCount = requestCount

        self.avgDurationMs = 0
        if avgDurationMs: self.avgDurationMs = int(avgDurationMs)

        self.avgMemUsedMb = int(avgMemUsedMb)
        self.memSizeMb = memSizeMb

        self.memUsedPct = 0.00
        if  memSizeMb: self.memUsedPct = round(float(100 * avgMemUsedMb/memSizeMb),2)

        self.startTs = startTs
        self.endTs = endTs
        self.elapsedMs = endTs - startTs

        self.avgTps = 0
        if  self.elapsedMs:
            self.avgTps = round((1000 * float(self.requestCount) / float(self.elapsedMs)),4)

        self.projectedPeriod = projectedPeriod
        self.projectedRequestCount = self.get_projected_request_count(requestCount)

        args = {'region':region, 'requestCount':self.projectedRequestCount,
                'avgDurationMs':math.ceil(avgDurationMs/100)*100, 'memoryMb':memSizeMb}
        print ("args: {}".format(args))
        self.projectedCost = lambdapricing.calculate(data.LambdaPriceDimension(**args))['totalCost']


    def get_projected_request_count(self,requestCount):
        result = 0
        print ("elapsed_ms:[{}] - period: [{}]".format(self.elapsedMs, self.projectedPeriod))
        if self.elapsedMs:
            result = float(requestCount)*(MS_MAP[self.projectedPeriod]/self.elapsedMs)
        return int(result)



"""
This class represents usage scenarios that will be modeled and displayed as possibilities, so the user can decide
if they're good options (or not) .
"""
class LambdaUtilScenario():
    def __init__(self, base_usage, proposedDurationMs, proposedMemSizeMb):

        self.memSizeMb = proposedMemSizeMb

        self.memUsedPct = 0
        self.memUsedPct = float(100 * base_usage.avgMemUsedMb/proposedMemSizeMb)

        self.durationMs = proposedDurationMs

        args = {'region':base_usage.region, 'requestCount':base_usage.projectedRequestCount,
                'avgDurationMs':self.durationMs, 'memoryMb':proposedMemSizeMb}
        self.cost= lambdapricing.calculate(data.LambdaPriceDimension(**args))['totalCost']
        self.savingsAmt = round((base_usage.projectedCost - self.cost),2)

        self.savingsPct = 0.00
        if base_usage.projectedCost:
            self.savingsPct = round((100 * self.savingsAmt / base_usage.projectedCost),2)
        self.timePeriod = MONTHLY

    def get_next_mem(self, memUsedMb):
      result = 0
      for m in consts.LAMBDA_MEM_SIZES:
        if memUsedMb <= float(m):
            result = m
            break
      return result





"""
This class takes an array of dictionary objects, so they can be converted to table format using Markdown syntax.
It also takes an optional array of labels, if you want to limit the output to a subset of keys in each dictionary.
The output is something like this:


             key1|              key2|               key3
              ---|               ---|                ---
               01|                02|                 03
               04|                05|                 06
               07|                08|                 09


"""

class ResultsTable():
    def __init__(self, records,labels):
        self.records = records
        self.labels = []
        if labels:
            self.labels = labels


    #Converts an array of dictionaries to Markdown format.

    def dict2md(self):
        result = ""
        keys = []
        if self.labels:
            keys = self.labels
        else:
            if self.records: keys = self.records[0].keys()

        rc = 0 #rowcount
        mdrow = "" #markdown headers row
        self.records.insert(0,[])#insert dummy record at the beginning, since first record in loop is used to create row headers
        for r in self.records:
            #if rc==0: keys = r.keys()
            cc = 0 #column count
            for k in keys:
                cc += 1
                if rc==0:
                    result +=  k
                    mdrow += self.addpadding(k,'---')
                else:
                    result += self.addpadding(k,r[k])
                if cc == len(keys):
                    result += "\n"
                    mdrow += "\n"
                else:
                    result += "|"
                    mdrow += "|"
            if rc==0: result += mdrow
            rc += 1
        return result



    """
    def dict2md(self):
        result = ""
        keys = []
        if self.labels:
            keys = self.labels
        else:
            if self.records: keys = self.records[0].keys()

        rc = 0 #rowcount
        mdrow = "" #markdown headers row
        for r in self.records:
            #if rc==0: keys = r.keys()
            cc = 0 #column count
            for k in keys:
                cc += 1
                if rc==0:
                    result +=  k
                    mdrow += self.addpadding(k,'---')
                else:
                    result += self.addpadding(k,r[k])
                if cc == len(keys):
                    result += "\n"
                    mdrow += "\n"
                else:
                    result += "|"
                    mdrow += "|"
            if rc==0: result += mdrow
            rc += 1
        return result
    """


    def addpadding(self,label,value):
        padding = ""
        i = 0
        while i < (len(label)-len(str(value))):
            padding += " "
            i += 1
        return padding + str(value)


def validate(function, minutes):
  validation_ok = True
  validation_message = "\nValidationError:\n"

  try:
    lambdaclient.get_function(FunctionName=function)
  except ClientError as e:
    if e.response['Error']['Code'] == 'ResourceNotFoundException':
      validation_message += "Function [{}] does not exist, please enter a valid Lambda function\n".format(function)
    else:
      validation_message += "Boto3 client error when calling lambda.get_function"
    validation_ok = False

  if minutes <1:
    validation_message += "Minutes must be greater than 0\n"
    validation_ok = False

  if not validation_ok:
      raise errors.ValidationError(validation_message)

  return validation_ok



if __name__ == "__main__":
   main(sys.argv[1:])
