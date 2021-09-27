import pymarc
from pymarc import MARCReader
import sys
import datetime
import os.path
import codecs
from tqdm import tqdm
import requests as r
import json
from lxml import etree
import io
import aiohttp
import asyncio
from asyncio_throttle import Throttler


def usage():
    """Print a usage statement for this script."""
    print("Usage:")
    print("  west1_extract_MMS_IDs.py <file.mrc> <apiKey>")
    print("Where:")
    print("  file.mrc          Binary MARC21 export of items")
    print("  APIKEY            API key for accessing Alma REST APIs")


def fileCheck(filename):
    """Determines if file 'filename' exists."""
    if not os.path.isfile(filename):
        print("File: " + filename + " not found. Exiting...")
        sys.exit(1)


async def GetHoldingIDs_async(mmsID, apikey, client, throttler):
    async with throttler:
        try:
            resp = None
            headers = {"accept": "application/json"}
            async with client.get(
                f"https://api-na.hosted.exlibrisgroup.com/almaws/v1/bibs/{mmsID}/holdings?apikey={apikey}",
                headers=headers,
            ) as session:
                if session.status != 200:
                    resp = await session.json()
                    session.raise_for_status()
                resp = await session.json()
                return {"mms_id": mmsID, "resp": resp}
        except Exception as e:
            print(
                f"GetHoldingIDs_async error -- Ex Libris API Error on mmsID {mmsID}: {e}"
            )


async def GetHoldingIDs_async_worker(mmsIDs, apikey):
    output = []
    throttler = Throttler(rate_limit=25)
    async with aiohttp.ClientSession() as client:
        awaitables = [
            GetHoldingIDs_async(mmsID, apikey, client, throttler) for mmsID in mmsIDs
        ]
        results = await asyncio.gather(*awaitables)
    for package in results:
        for holding in package["resp"]["holding"]:
            if "holding_id" in holding:
                output.append(
                    {"holding_id": holding["holding_id"], "mms_id": package["mms_id"]}
                )
    return output


async def GetHoldingXML_async(mmsID, holdingID, apikey, client, throttler):
    async with throttler:
        try:
            resp = None
            async with client.get(
                f"https://api-na.hosted.exlibrisgroup.com/almaws/v1/bibs/{mmsID}/holdings/{holdingID}?apikey={apikey}"
            ) as session:
                if session.status != 200:
                    resp = await session.text()
                    session.raise_for_status()
                resp = await session.text()
                xml = bytes(bytearray(resp, encoding="utf-8"))
                return {"mms_id": mmsID, "holding_id": holdingID, "xml": etree.XML(xml)}
        except Exception as e:
            print(
                f"GetHoldingXML_async error -- Ex Libris API Error on mmsID {mmsID} + holding {holdingID}: {e}"
            )


async def GetHoldingXML_async_worker(list_of_dicts, apikey):
    throttler = Throttler(rate_limit=25)
    async with aiohttp.ClientSession() as client:
        awaitables = [
            GetHoldingXML_async(
                keypair["mms_id"], keypair["holding_id"], apikey, client, throttler
            )
            for keypair in list_of_dicts
        ]
        results = await asyncio.gather(*awaitables)
    return results


def main(argv):
    if len(argv) != 3:
        usage()
        sys.exit(1)

    # input file
    inMarcFile = argv[1]
    apikey = argv[2]

    # filecheck inputs
    fileCheck(inMarcFile)

    mms_ids = []
    xml_block = ""

    outFile = (
        "asu.alma.archived." + (datetime.datetime.now()).strftime("%Y%m%d") + ".mrc"
    )

    # Parse the MARC file for the MMS IDs
    print("Extracting MMS IDs...")
    with open(inMarcFile, "rb") as fh:
        marcReader = MARCReader(fh, to_unicode=True, force_utf8=True)
        for record in marcReader:
            mms_ids.append(record["001"].value())
            # print(record["020"])
            if record["020"] and record["020"]["a"]:
                for x in record["020"]["a"]:
                    mms_ids.append(x.value())
    print(f"Extraction finished, {len(mms_ids)} MMS ID(s) extracted.")

    # print("Gathering Holding IDs...")
    # for mms_id in tqdm(mms_ids):
    # gotten_holding_ids = GetHoldingIDs(mms_id, apikey)
    # for holding_id in gotten_holding_ids:
    # holding_ids.append({"holding_id": holding_id, "mms_id": mms_id})
    # print(f"{len(holding_ids)} holding ID(s) gathered.")

    print("Gathering Holding IDs...")
    holding_ids = asyncio.run(GetHoldingIDs_async_worker(mms_ids, apikey))
    print(f"{len(holding_ids)} holding ID(s) gathered.")

    print("Gathering Holding Record XML...")
    xml_data = asyncio.run(GetHoldingXML_async_worker(holding_ids, apikey))

    print("Parsing Holding Record XML...")
    xml_block += "<collection>"
    counter = 0
    for data_dict in tqdm(xml_data):
        holdingXML = data_dict["xml"]

        if holdingXML.find('.//datafield[@tag="583"]') is not None:
            # add/replace 001 field with holdingID
            if holdingXML.find('.//controlfield[@tag="001"]') is None:
                cf001 = etree.Element("controlfield", tag="001")
                cf001.text = data_dict["holding_id"]
                holdingXML.find("record").insert(2, cf001)
            else:
                holdingXML.find('.//controlfield[@tag="001"]').text = data_dict[
                    "holding_id"
                ]

            # add/replace 003 field with AzTeS
            if holdingXML.find('.//controlfield[@tag="003"]') is None:
                cf003 = etree.Element("controlfield", tag="003")
                cf003.text = "AzTeS"
                i = 0
                cfields = holdingXML.findall(".//controlfield")
                while i < len(cfields) and int(cfields[i].get("tag")) < 3:
                    i += 1
                # i = 2
                # the ith control field is where you should insert 003 before
                # this is actually <record>'s (i+1)-child as leader is 0th
                holdingXML.find("record").insert(i + 1, cf003)
            else:
                holdingXML.find('.//controlfield[@tag="003"]').text = "AzTeS"

            # replace/add 004 field with mmsID
            if holdingXML.find('.//controlfield[@tag="004"]') is None:
                cf004 = etree.Element("controlfield", tag="004")
                cf004.text = data_dict["mms_id"]
                # find the tag that 004 should come before
                i = 0
                cfields = holdingXML.findall(".//controlfield")
                while i < len(cfields) and int(cfields[i].get("tag")) < 4:
                    i += 1
                # i = 3
                # the ith control field is where you should insert 004 before
                # this is actually <record>'s (i+1)-child as leader is 0th
                holdingXML.find("record").insert(i + 1, cf004)
            else:
                holdingXML.find('.//controlfield[@tag="004"]').text = data_dict[
                    "mms_id"
                ]

            # add/replace 005 field with ISO date
            date = datetime.datetime.now().isoformat()
            date = date.replace(":", "").replace("-", "").replace("T", "")
            date = date.split(".")
            date = date[0] + "." + date[1][:2]
            if holdingXML.find('.//controlfield[@tag="005"]') is None:
                cf005 = etree.Element("controlfield", tag="005")
                cf005.text = date
                # find the tag that 005 should come before
                i = 0
                cfields = holdingXML.findall(".//controlfield")
                while i < len(cfields) and int(cfields[i].get("tag")) < 5:
                    i += 1
                # i = 4
                # the ith control field is where you should insert 005 before
                # this is actually <record>'s (i+1)-child as leader is 0th
                holdingXML.find("record").insert(i + 1, cf005)
            else:
                holdingXML.find('.//controlfield[@tag="005"]').text = date

            xml_block += etree.tostring(
                holdingXML.find("record"), pretty_print=False
            ).decode("utf-8")
            counter += 1
    xml_block += "</collection>"
    print(f"{counter} Holding Records(s) gathered.")

    print("Converting from MARCXML to a MARC21 binary file...")
    writer = codecs.open(outFile, "wb", "utf-8")
    marc_records = pymarc.parse_xml_to_array(io.StringIO(xml_block))
    count = 0
    for rec in marc_records:
        # force utf-8
        rec.force_utf8 = True
        # skip over any entries that have an empty 583 field
        if len(rec.get_fields("583")) == 0:
            print(
                "Blank 583 field: skipping "
                + rec["001"].value()
                + " / "
                + rec["004"].value()
            )
            continue
        count += 1
        # get string representation of marc
        marc = rec.as_marc()
        # decode character set
        marc = marc.decode("utf-8")
        # output
        writer.write(marc)

    print(f"Finished. {count} MARCXML records converted to MARC21 binary.")


if __name__ == "__main__":
    main(sys.argv)
