from flask import Flask, render_template, request, redirect, Response, jsonify
from flask_material import Material
import json 
import requests
from datetime import datetime as dt
from datetime import timedelta
import datetime
import math
 
app = Flask(__name__)
Material(app)

map_api_key = "AIzaSyB9tMqE0I_YflM58z-xT2BKwMYS_vYLUC4"
weather_api_key = "608106f00cd6ffa63e84fd29e4808bd3"

direction_prefix = "https://maps.googleapis.com/maps/api/directions/json?origin=_origin_value_&destination=_destination_value_&key="
reverse_geo_prefix = "https://maps.googleapis.com/maps/api/geocode/json?latlng=_lat_val_,_long_val_&key="
forecast_prefix = "https://api.openweathermap.org/data/2.5/onecall?lat=_lat_val_&lon=_long_val_&appid="
static_map_prefix = "https://maps.googleapis.com/maps/api/staticmap?center=_center_lat_val_,_center_long_val_&zoom=_zoom_val_&size=_size_val_x_size_val_&_marker_string_&key="

src = "Bangalore"
dest = "Agra"
n = 15
pixel_width = 800
GLOBE_WIDTH = 256

@app.route('/')
def index():
	return render_template('index.html')

@app.route('/receiver', methods = ['POST'])
def worker():
	# read json + reply
	print("Enter")
	print(request)
	data = request.get_json()
	print(data)
	source = data[0]["source"]
	destination = data[0]["destination"]
	print(source)
	print(destination)
	result = get_center_and_markers_json(source, destination)
	print(result)
	return jsonify(result)

	'''for item in data:
		# loop over every row
		result += str(item['make']) + '\n'

	return result'''

def get_approx_mid(a, b):
    mid = {}
    mid["lat"] = (a["lat"]+b["lat"])/2
    mid["lng"] = (a["lng"]+b["lng"])/2
    return mid

def get_directions(src, dest):
    url = direction_prefix.replace("_origin_value_", src)
    url = url.replace('_destination_value_', dest)
    url = url + map_api_key
    response = requests.get(url)
    response_json = response.json()
    route1 = response_json["routes"][0]
    bounds = route1["bounds"];
    points = []
    turns = route1["legs"][0]["steps"];
    start_time = dt.now()
    prev_duration = 0
    for turn in turns:
        duration = turn["duration"]["value"]
        diff = timedelta(seconds = (prev_duration + int(duration/2)))
        point = {}
        point["time"] = start_time + diff
        point["location"] = get_approx_mid(turn["end_location"], turn["start_location"])
        points.append(point)
        prev_duration += duration
    return bounds, points
                                
def get_n_points(points, n):
    m = len(points)
    if (n>=m):
        return points
    interval = int(math.ceil(m/n))
    ret_pts = points[::interval]
    if (ret_pts != points[m-1]):
        ret_pts.append(points[m-1])
    return ret_pts                      

def get_json_at_lat_long(prefix, key, loc):
    url = prefix.replace("_lat_val_", str(loc["lat"]))
    url = url.replace('_long_val_', str(loc["lng"]))
    url = url + key
    response = requests.get(url)
    return response.json()
    
def reverse_geo_coding(loc):
    response_json = get_json_at_lat_long(reverse_geo_prefix, map_api_key, loc)
    addr_comp = response_json["results"][0]["address_components"]
    return addr_comp[len(addr_comp)-1]["short_name"]
    
def get_forcast_at(point):
    response_json = get_json_at_lat_long(forecast_prefix, weather_api_key, point["location"])
    hourly_weather = response_json["hourly"]
    prev_diff = timedelta(seconds = 345600)
    prev_cloudy = 0
    got_min = False
    for weather in hourly_weather:
        weather_time = datetime.datetime.fromtimestamp(weather["dt"])
        cloudy = weather["clouds"]
        diff = abs(point["time"] - weather_time)
        if (not got_min) and diff < prev_diff:
            got_min = True
        if got_min and diff>=prev_diff:
            return prev_cloudy
        prev_cloudy = cloudy
        prev_diff = diff
    return 0
    
    
def get_precipitation_at(point):
    return get_forcast_at(point["location"], point["time"])
    
 

def get_precipitation(points):
    prev_zip = 0
    prev_prec_point = 0
    prec_points = []
    for point in points:
        cur_zip = reverse_geo_coding(point["location"])
        if (cur_zip == prev_zip):
            prec_points.append(prev_prec_point)
            continue
        prec_point = {}
        precipitation = get_forcast_at(point)
        prec_point["point"] = point
        prec_point["precipitation"] = precipitation
        prec_point["zip"] = cur_zip
        prec_points.append(prec_point)
        prev_prec_point = prec_point
        prev_zip = cur_zip
    return prec_points

def get_center(bounds):
    return get_approx_mid(bounds["northeast"], bounds["southwest"])

def get_zoom(bounds):
    west = bounds["southwest"]["lng"]
    east = bounds["northeast"]["lng"]
    angle = east - west;
    if angle < 0 :
        angle += 360
    return round(math.log(pixel_width * 360 / angle / GLOBE_WIDTH) / math.log(2))


def get_marker_string(points):
    marker_string = ""
    color_map = ["green", "yellow", "orange", "red", "red"]
    marker_prefix = "&markers=size:tiny%7Ccolor:_color_val_%7Clabel:_label_val_%7C_lat_val_,_long_val_"
    for point in points:
        label = point["precipitation"]
        color = color_map[int(label/25)]
        label = str(label)
        marker = marker_prefix.replace("_color_val_", color)
        marker = marker.replace("_label_val_", label)
        marker = marker.replace("_lat_val_", str(point["point"]["location"]["lat"]))
        marker = marker.replace("_long_val_", str(point["point"]["location"]["lng"]))
        marker_string += marker
    return marker_string

def get_map_url(center, zoom, marker_string, zoom_fix = 4):
    url = static_map_prefix.replace("_center_lat_val_", str(center["lat"]))
    url = url.replace('_center_long_val_', str(center["lng"]))
    url = url.replace('_zoom_val_', str(zoom-zoom_fix))
    url = url.replace('_size_val_', str(pixel_width))
    url = url.replace('_marker_string_', marker_string)
    url = url + map_api_key
    return url
     
def get_weather_map_enroute(source = src, destination = dest, N = n, zoom_fix = 4):
    bounds, points = get_directions(source, destination)
    n_points = get_n_points(points, N)
    precipitation_at_points = get_precipitation(n_points)
    map_url = get_map_url(get_center(bounds), get_zoom(bounds), get_marker_string(precipitation_at_points), zoom_fix)
    return map_url

def get_markers(points):
    marker_list = []
    color_map = ["green", "yellow", "orange", "red", "red"]
    for point in points:
        label = point["precipitation"]
        color = color_map[int(label/25)]
        label = str(label)
        marker = {}
        marker["color"] = color
        marker["label"] = label
        marker["lat"] = point["point"]["location"]["lat"]
        marker["lng"] = point["point"]["location"]["lng"]
        marker_list.append(marker)
    return marker_list

def get_center_and_markers_json(source = src, destination = dest, N = n, zoom_fix = 4):
    bounds, points = get_directions(source, destination)
    n_points = get_n_points(points, N)
    precipitation_at_points = get_precipitation(n_points)
    center = get_center(bounds)
    markers = get_markers(precipitation_at_points)
    json_obj = {}
    json_obj["center"] = center
    json_obj["markers"] = markers
    return json_obj

if __name__ == '__main__':
	app.run(debug=True)
