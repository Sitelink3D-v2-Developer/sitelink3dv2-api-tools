# AsBuilt Live Cesium Map Viewer

## Background
Being up to date with the current live AsBuilt status of a job site is powerful. Tooling that radiates such live data allows site managers to identify when productivity is not as expected and remedy the issues before schedules and budgets are significantly impacted.

The AsBuilt Live Cesium Map Viewer has two purposes:
1. Provide an out-of-the-box stand-alone tool to view AsBuilt Live activity at any Sitelink3D v2 site.
2. Demonstrate how interaction with the Sitelink3D v2 AsBuilt Live and RDM services is accomplished.

## Usage
The following process describes the use of the viewer:

- Configure the HTML.
- Configure the site details.
- Select the desired AsBuilt parameters.

### Configure the HTML
In order to use this tool, a free Cesium Ion token is required. This can be obtained from https://cesium.com/ion/tokens. The token needs to be assigned to the ```Cesium.Ion.defaultAccessToken``` variable in the ```CesiumAsBuilt.html```. The HTML file can then be opened in a browser. The absence of a globe in the Cesium window is symptomatic of a missing or invalid Ion token.

### Configure the Site Details
The tool requires the following site configuration which is entered into the browser:

- Environment.
- Site Identifier.
- JWT.

The selection of cloud environment is detailed [here](https://github.com/Sitelink3D-v2-Developer/sitelink3dv2-examples#select-a-cloud-environment). Obtaining the site identifier for your site is detailed [here](https://github.com/Sitelink3D-v2-Developer/sitelink3dv2-examples#site-identifier) and accessing a JWT for the site is detailed [here](https://github.com/Sitelink3D-v2-Developer/sitelink3dv2-examples#jwt). Once populated, click on the green ```View``` button to load the available metadata from the specified site.

### Select the Desired AsBuilt Parameters
Before AsBuilt data can be rendered on the map, the following options need to be selected based on the data available at the site:
- Task.
- Sequence.
- AsBuilt View / Color Map.
