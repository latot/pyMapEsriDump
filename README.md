# Scrapping of Arcgis Server

This project is to can download all the data and maps we can from a Arcgis Server, not a particular map or layer.

Think of this, like a tool for a Data Lake.

This project does not only focus in download, the idea is:

- Keep the integrity of the data
- Keep the original data
- Keep traceability of the data

What is to avoid:

- Transformations of the CRS
- Adjustments of the data

**CRS transformation**

Transform the CRS is not a perfect calculation, there is error, so the idea minimize the error, for that there is some ways, in both the original data must be keep:

- Wait new technologies like WKT2: [Super WKT2](https://inbo.github.io/tutorials/tutorials/spatial_crs_coding/)
- Store the original data, and transform only when you want to use it, or at least, keep the original data and a copy with the transformations
- Minimize the number of times we transform the CRS

**Adjustments of the data**

Lets pick as example the shp files, they don't allow some symbols, or have a size limit, is very tempting apply some adjustments to the data to can use it, but, with this changes it will not be the same data as the server, if you try to set a limit in the column names (shp have a limit of characters) you need to remove data, sacrifice it, that is not good, this changes and temptations, put in risk the integrity of the data and their traceability.

## Download

To can use this project, sadly for now is just copy/paste the script, or clone it:

```
git clone https://github.com/latot/pyMapEsriDump
```

## How to use

We can know this with the help of the script:

```
usage: MapDump.py [-h] [--proxy [PROXY]] [--timeout [TIMEOUT]] [--start_folder [START_FOLDER]] url folder

Dump Map Server

positional arguments:
  url                   url map server
  folder                output folder

optional arguments:
  -h, --help            show this help message and exit
  --proxy [PROXY]       proxy url
  --timeout [TIMEOUT]   Timeout to get response from the server in seconds
  --start_folder [START_FOLDER]
                        From what server folder start reading
```

The script is not perfect, and very..., ugly internally, but for now works...

What is not supported? Download directly a map the ```start_folder```, you only can choose a map of the server to download a section.

## About Arcgis Server

The server stores several features, maps, layers and services, the objective of this project is download everything.

Here is an example of a server ```https://sampleserver6.arcgisonline.com/arcgis/rest/services```

You can travel over all the services in the link, this project will download everything supported from there in a folder, will keep every new service or feature in a new one inside, lets pick an example:

```https://sampleserver6.arcgisonline.com/arcgis/rest/services/Energy/Geology/MapServer```

The folder where the map will be saved is ```Energy/Geology/MapServer```, in this case, if we check the Map, we can notice this will not have any spatial data inside, this is because every map of Arcgis have several layers, and the data in the server is there, in the layers.

Every layer and map have info stored in Arcgis, you can read it in ```data.json```.

Some layers will be empty, because Arcgis can have a layer composed by layers, this is like, this map have 10 layers, from 0 to 9, and the layers 3, 4, 5 will be contained in the layer 2, you will see something like:

```
├── 0
├── 1
├── 2
├── ├── 3
├── ├── 4
├── ├── 5
├── 6
├── 7
├── 8
├── 9
```

The server don't necessary have a record of what means a map, a layer or their columns, lets remember they are written by people, and is in their own to describe it, the maps are not safe from human mistakes.

How can we download the server above?

```
python3 MapDump.py "https://sampleserver6.arcgisonline.com/arcgis/rest/services" "folder"
```

If we want to not download all, only the Energy folder:

```
#url: https://sampleserver6.arcgisonline.com/arcgis/rest/services/Energy
python3 MapDump.py "https://sampleserver6.arcgisonline.com/arcgis/rest/services" "folder" --start_folder "Energy"
```