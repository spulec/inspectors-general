from utils import utils
import os
import re
import logging
import datetime
import urllib.parse

# Save a report to disk, provide output along the way.
#
# 1) download report to disk
# 2) extract text from downloaded report using report['file_type']
# 3) write report metadata to disk
#
# fields used: file_type, url, inspector, year, report_id
# fields added: report_path, text_path

def save_report(report):
  options = utils.options()

  # create some inferred fields, set defaults
  preprocess_report(report)

  # validate report will return True, or a string message
  validation = validate_report(report)
  if validation != True:
    raise Exception("[%s][%s][%s] Invalid report: %s\n\n%s" % (
      report.get('type'), report.get('published_on'), report.get('report_id'),
      validation, str(report)))

  logging.warn("[%s][%s][%s]" % (report['type'], report['published_on'], report['report_id']))

  if options.get('dry_run'):
    logging.warn('\tskipping download and extraction, dry_run == True')
  elif report.get('unreleased', False) is True:
    logging.warn('\tno download/extraction of unreleased report')
  else:
    report_path = download_report(report)
    if not report_path:
      logging.warn("\terror downloading report: sadly, skipping.")
      return False

    logging.warn("\treport: %s" % report_path)

    text_path = extract_report(report)
    logging.warn("\ttext: %s" % text_path)

  data_path = write_report(report)
  logging.warn("\tdata: %s" % data_path)

  return True


# Preprocess before validation, to catch cases where inference didn't work.
# So, fields may be absent at this time.
def preprocess_report(report):
  # not sure what I'm doing with this field yet
  if report.get("type") is None:
    report["type"] = "report"

  # if we have a date, but no explicit year, extract it
  if report.get("published_on") and (report.get('year') is None):
    report['year'] = year_from(report)

  # if we have a URL, but no explicit file type, try to detect it
  if report.get("url") and (report.get("file_type") is None):
    parsed = urllib.parse.urlparse(report['url'])
    split = parsed.path.split(".")
    if len(split) > 1:
      report['file_type'] = split[-1]



# Ensure required fields are present
def validate_report(report):
  required = (
    "published_on", "report_id", "title", "inspector", "inspector_url",
    "agency", "agency_name",
  )
  for field in required:
    value = report.get(field)
    if (value is None) or value == "":
      return "Missing a required field: %s" % field

  # URL is not required in the case that the report has an 'unreleased' field
  # set to True
  unreleased = report.get('unreleased', False)
  if unreleased is not True:  # Strict test for True specifically
    url = report.get("url")
    if not url:
      return "Missing required field 'url' when field 'unreleased' != True"

  # report_id can't have slashes, it'll mess up the directory structure
  if "/" in report["report_id"]:
    return "Invalid / in report_id - find another way: %r" % report["report_id"]

  if report.get("year") is None:
    return "Couldn't get `year`, for some reason."

  if report.get("type") is None:
    return "Er, this shouldn't happen: empty `type` field."

  if unreleased is not True and report.get("file_type") is None:
    return "Couldn't figure out `file_type` from URL, please set it explicitly."

  try:
    datetime.datetime.strptime(report['published_on'], "%Y-%m-%d")
  except ValueError:
    return "Invalid format for `published_on`, must be YYYY-MM-DD."

  if re.search("(\\-\\d[\\-]|\\-\\d$)", report["published_on"]):
    return "Invalid format for `published_on`, dates must use zero prefixing."

  return True


def download_report(report):
  report_path = path_for(report, report['file_type'])
  binary = (report['file_type'].lower() == 'pdf')

  result = utils.download(
    report['url'],
    "%s/%s" % (utils.data_dir(), report_path),
    {'binary': binary}
  )
  if result:
    return report_path
  else:
    return None

# relies on putting text next to report_path
def extract_report(report):
  report_path = path_for(report, report['file_type'])

  file_type_lower = report['file_type'].lower()
  if file_type_lower == "pdf":
    return utils.text_from_pdf(report_path)
  elif file_type_lower.startswith("htm"):
    return utils.text_from_html(report_path)
  else:
    logging.warn("Unknown file type, don't know how to extract text!")
    return None

def write_report(report):
  data_path = path_for(report, "json")

  utils.write(
    utils.json_for(report),
    "%s/%s" % (utils.data_dir(), data_path)
  )
  return data_path


def path_for(report, ext):
  return "%s/%s/%s/report.%s" % (report['inspector'], report['year'], report['report_id'], ext)

def cache(inspector, path):
  return os.path.join(utils.cache_dir(), inspector, path)

# get year for a report from its publish date
def year_from(report):
  return int(report['published_on'].split("-")[0])

# assume standard options for IG scrapers, since/year
def year_range(options):
  this_year = datetime.datetime.now().year

  since = options.get('since')
  if type(since) is not str: since = None
  if since:
    since = int(since)
    if since > this_year:
      since = this_year

  year = options.get('year')
  if year:
    year = int(year)
    if year > this_year:
      year = this_year

  if since:
    year_range = list(range(since, this_year + 1))
  elif year:
    year_range = list(range(year, year + 1))
  else:
    year_range = list(range(this_year, this_year + 1))

  return year_range
