# Datalogger Haul Simulator (Pathinator)

## Introduction

This Linux tool simulates a number of haul trucks and excavators operating at a site. In particular:

1. Trucks drive configurable routes which facilitate hauls that appear to run on roads visible on a map.
2. Each truck is configured with a delayed start so vehicle spacing looks realistic.
3. Events that simulate real haul activity are sent including delays, loads, dumps and payload onboard weighing (OBW).
4. Metadata (RDM objects) including materials, regions and operators are injected into the site for a realistic experience.

This is an excellent tool for the purposes of:

1. Providing data to verify Sitelink3D v2 API integration including the creation of reports with realistic content.
2. Facilitating demonstrations of site activity simulated at any desired physical location.

Because of the way the simulated trucks follow predefined paths, we internally refer to this tool affectionately as _The Pathinator_.

## Using Pathinator

The Pathinator is controlled using a shell script. A complete demonstration of its use is available under the `videos` folder in this repository. Running the simulation is achieved as follows: 

1. Edit the `pathinator.sh` file.
2. Populate the configuration in the `Mandatory settings` sections at the top of the file:
- `DC` is one of `us` or `eu` depending on the data center hosting the site.
- `DEPLOY_ENV` is one of `qa` or `prod`.
- `REGION` is one of `small`, `medium` or `large`.
- `SITE` is the unique hexadecimal site identifier.

3. At a console run `pathinator.sh start`.
4. View the site in the Sitelink3D v2 web portal to observe machine activity noting that the machines started with configurable staggered time offsets.
5. At the console run `pathinator.sh tail` to view logs during execution.
6. At the console run `pathinator.sh stop` when finished with simulation.

Sensible default values are provided in the script where possible. Note that QA sites reside exclusively in the US. An instructional video demonstrating this configuration is available in this repository.

## More Detailed Information

### Run files

The following files are used to run the simulation. Only the last one needs configuration.

- pathinator.sh  - the "Mandatory Settings" section should be configured appropriately.
- minder.sh      - script to restart simulation on error.
- distribution   - golang executable.

### Config Files

All configuration beyond the `Mandatory Settings` mentioned above is provided by default and does not need to be altered. Additional configuration listed below can however be modified to provide a more bespoke simulation as required. 

The following configurations are used by the simulator:

- Machine Definitions
    - A file containing a single json object.
    - This object specifies the machines of a particular type to simulate.
    - Other characteristics are also specified such as machine speed.
    - Default examples are `trucks.json` and `excavator.json`.

- Machine Paths
    - A file containing an array of JSON objects.
    - Each object specifies a position and other replay data such as load and dump events.
    - The simulator will move machines to the next point at the current speed.
    - Default examples are `trucks.path.json` and `excavator.path.json`.

- RDM Data
    - A file containing JSON blobs in JSONL line format.
    - Each line represents a site object such include regions, operators, machines and delays.
    - These are inserted into the site on startup.
    - Default example is `state.jsonl`.

### Machine Definition Files

Each machine definition file defines the following information:

- num_hauls : number of hauls to run using this config.
- interval  : number of seconds between finishing one haul and starting the next.
- grain     : how often to send positions, in seconds.
- machines  : an array of the following data:
    - machine  : the URN of the machine.
    - device   : the URN of the device.
    - operator : the UUID of the first operator on the machine [the path file may change this].
    - delay_seconds : how many seconds between starting machines [to avoid multiple machines appearing to crash into each other].
- path_file     : the path file that these machines use
- fixture_files : an array of RDM data files loaded at startup.

### Path Files

Each path file defines the following information:

- An array of json objects.
- Each object defines a `point` and other optional data.
- The simulator will move machines to the next point at the current speed.

The basic optional data includes:

- action: event such as "load", "dump", "close" to implement the haul cycle.
- delay : follow this move with a delay for this many seconds.
- delay_name : use this name to describe the delay as defined by the RDM delay object.
- material : set the RDM material by name.
- ns : set the namespace used for state information (usually "topcon.rdm.list").
- quantity : set the quantity of material being hauled.
- region : set the RDM region by name.
- speed : new speed in m/s.
- task : set the RDM task by name.

There's also `material_id`, `region_id`, and `task_id`; they set the corresponding fields given their IDs instead of names.

The advanced optional data includes:

- data: a json field giving extra key,value pairs included in the generated datalogger packets. An example is loader information for the processing of onboard weighing (OBW) events. 
- state: a json object mapping namespaces to key,value pairs which define additional "sitelink::State" datalogger packets.
- topo_point: set a topo point.

### RDM Data File

Typically the easiest way to make one of these is to set up everything you want on your site and then extract the RDM data into a file.
