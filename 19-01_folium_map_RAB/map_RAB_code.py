#Import libraries
import folium
from folium.plugins import MarkerCluster
import pandas as pd

#Load data
data = pd.read_csv('map_RAB_data.csv', delimiter=';')
location = data['location']
duration = data['duration']
lat = data['lat']
lon = data['lon']


# Dict for fill colors
loc_colors = {'Lausanne': '#99FFFF',
              'Genf': '#00FFFF',
              'Basel': '#00CCCC',
              'Zürich': '#009999'
                }

#Create base map
map = folium.Map(location=[46.7985624, 8.2319736], 
                 zoom_start = 8.2, 
                 tiles = "Mapbox bright"
                 )

#Plot Markers
for lat, lon, duration, location in zip(lat, lon, duration, location):
    folium.CircleMarker(location=[lat, lon], 
                        radius = duration / 3, 
                        popup=str(location), 
                        fill_color=loc_colors[location], 
                        color="#006666", 
                        fill_opacity = 0.7
                        ).add_to(map)

#Save the map
map.save("map1.html")