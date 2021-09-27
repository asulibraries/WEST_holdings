# WEST Holdings Script (aka Getting Holdings Records from Alma)
This script has been modified for ASU specifics. Thanks to Kate Deibel for the excellent code.

## Background
For our commitment to services like WEST, we have to provide holding records. Unfortunately, there is no direct way to export holding records from Alma. Using ideas from [Bill Kelm's approach](https://github.com/hatfieldlibrary/alma-holdings-records), this repository contains a series of scripts for extracting holding records via the Alma REST APIs.

## Usage ##
```
west1_extract_MMS_IDs.py <file.mrc> <apiKey>
```
Where:
-    file.mrc   --    Binary MARC21 export of items
-    APIKEY     --    Your API key for accessing Alma REST APIs

### Generate and Export a Set ###
1. Create a set in Alma of the desired items.
2. Export said set using the *Export Bibliographic Records* job to generate a MARC21 file (holdings information does not need to be added).

### Extraction and API Calls ###
To get the holding records, both an MMS ID and a Holding ID are needed for the [Retrieve Holdings Record](https://developers.exlibrisgroup.com/alma/apis/bibs/) web service. To get these two IDs, the following is performed:

1. Extract the MMS ID from the '001' fields in the exported MARC data
2. Use the MMS ID and call the [Retrieve Holdings List](https://developers.exlibrisgroup.com/alma/apis/bibs/) web service and extract the Holding IDs from the returned XML
3. Use the two IDs to get the holdings record via the *Retrieve Holdings Record* web service.
4. Convert the returned XML data back into MARC21 (while skipping over records lacking a 583 field).

## ASU-Specific Modifications
The original code has been modified for ASU use -- specifically, it now utilizes asynchronous API requests which drastically reduces the runtime from several hours to approximately 15-20 minutes.

Ultimately, it accomplishes the following:
1. exports a set of bib records from Alma
2. extracts the MMSIDs from (1) bib records
3. gets the holding IDs for each of the MMSIDs from (2)
4. gets each of the holding records, if it has a data field with tag 583, then
  a. sets the 001 is the holding id
  b. sets the 003 to AzTes
  c. sets the 004 to the bib MMSID
  d. sets the 005 to the ISO date
5. converts generated xml from above back to marc binary

## License
This code is released under the OpenBSD license:

Copyright (c) 2015 Katherine Deibel. Permission to use, copy, modify, and distribute this software for any purpose with or without fee is hereby granted, provided that the above copyright notice and this permission notice appear in all copies.

THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.
