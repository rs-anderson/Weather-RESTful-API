from flask import Flask, request, jsonify, send_file
import requests
import json
from functools import reduce
import itertools
from datetime import date, datetime
from statistics import median
import matplotlib.pyplot as plt
import numpy as np

# get the Visual Crossing API key
with open("./visual_crossing_api_key.txt", "r") as file:
    API_KEY = file.readline()


app = Flask(__name__)


def average(lst): 
    return reduce(lambda a, b: a + b, lst) / len(lst) 


def period_to_start_end(period):
    """ converts period format to start and end dates """
    start = period.split('|')[0]
    end = period.split('|')[1]
    return start, end

def get_num_days(start, end):
    """ returns the number of days between the start and end date """
    start_date = datetime.strptime(start, '%Y-%m-%d')
    end_date = datetime.strptime(end, '%Y-%m-%d')
    delta = end_date - start_date
    return delta.days + 1


def get_num_obs(start, end, aggregator):
    """ returns the number of visual crossing weather observations that fall within the period """
    num_days = get_num_days(start, end)
    num_hours = num_days*24
    num_obs = num_hours//aggregator
    return num_obs


def get_weather(city, start, end):
    """ general function for retrieving the weather data """
    aggregator = 1
    num_obs = get_num_obs(start, end, aggregator)
    while num_obs > 100:
        if aggregator == 24:
            return 'Period is too long for Weather Crossing API.', 1
        aggregator += 1
        num_obs = get_num_obs(start, end, aggregator)
    url = f'https://weather.visualcrossing.com/VisualCrossingWebServices/rest/services/weatherdata/history?&aggregateHours={aggregator}&startDateTime={start}T00:00:00&endDateTime={end}T00:00:00&unitGroup=uk&contentType=json&dayStartTime=0:0:00&dayEndTime=0:0:00&location={city}&key={API_KEY}'
    # HTTP requests
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.json(), 0
    except requests.exceptions.HTTPError as e:
        return e, 1

 

def is_valid_dates(start, end):
    """ checks if the dates are valid """
    try:
        start_date = datetime.strptime(start, '%Y-%m-%d')
        end_date = datetime.strptime(end, '%Y-%m-%d')
        delta = end_date - start_date
        return delta.days >= 0
    except:
        return False

def get_weather_results(city, period):
    """ function that gets the weather data, computes the statistics and stores the results in a dictionary """
    weather_summary = {}

    try:
        start_date, end_date = period_to_start_end(period)
    except:
        error = "Your period is invalid. The correct format is 'start_date|end_date' in the following date format '%Y-%m-%d|%Y-%m-%d'."
        return error, 1

    if not is_valid_dates(start_date, end_date):
        error = "Your dates are invalid. Either they are formatted incorrectly (the correct date format is '%Y-%m-%d') or the end date is before the start date."
        return error, 1

    weather_json, status = get_weather(city, start_date, end_date)
    
    if status == 1:
        error = weather_json
        return error, 1

    if 'errorCode' in weather_json:
        error = weather_json['message']
        return error, 1
    
    weather_periods_info = weather_json['locations'][city]['values']
    
    temps = [weather_dict['temp'] for weather_dict in weather_periods_info]
    min_temps = [weather_dict['mint'] for weather_dict in weather_periods_info]
    max_temps = [weather_dict['maxt'] for weather_dict in weather_periods_info]
    humidities = [weather_dict['humidity'] for weather_dict in weather_periods_info]

    weather_summary['average_temp'] = round(average(temps), 2)
    weather_summary['median_temp'] = round(median(temps), 2)
    weather_summary['min_temp'] = min(min_temps)
    weather_summary['max_temp'] = max(max_temps)

    weather_summary['average_humidity'] = round(average(humidities), 2)
    weather_summary['median_humidity'] = round(median(humidities), 2)
    weather_summary['min_humidity'] = min(humidities)
    weather_summary['max_humidity'] = max(humidities)

    return weather_summary, 0


@app.route('/weather')
def weather_conditions():
    """ endpoint for weather summary """
    city  = request.args.get('city', None, type=str)
    period  = request.args.get('period', None, type=str)
   
    weather_results, indicator = get_weather_results(city, period)
    if indicator == 1:
       return f'Error: {weather_results}' 
    return jsonify(weather_results)


@app.route('/weather/bar')
def bar_summary():
    """ endpoint for bar graphs """
    city  = request.args.get('city', None, type=str)
    period  = request.args.get('period', None, type=str)
   
    weather_results, indicator = get_weather_results(city, period)
    if indicator == 1:
       return f'Error: {weather_results}' 

    objects = ('Min', 'Median', 'Mean', 'Max')
    y_pos = np.arange(len(objects))

    try:
        performance = [
            weather_results['min_temp'],
            weather_results['median_temp'],
            weather_results['average_temp'],
            weather_results['max_temp']
            ]
        # Plot in different subplots
        fig, (ax1, ax2) = plt.subplots(1, 2)

        ax1.bar(y_pos, performance, align='center', alpha=0.5)
        ax1.set_xticks(y_pos)
        ax1.set_xticklabels(objects)
        ax1.set_ylabel('Degrees Celcius')
        ax1.set_title('Summary Statistics for \n Temperature')

        performance = [
            weather_results['min_humidity'],
            weather_results['median_humidity'],
            weather_results['average_humidity'],
            weather_results['max_humidity']
            ]

        ax2.bar(y_pos, performance, align='center', alpha=0.5)
        ax2.set_xticks(y_pos)
        ax2.set_xticklabels(objects)
        ax2.set_ylabel('Percentage (%)')
        ax2.set_title('Summary Statistics for \n Humidity')
        fig.tight_layout()
        fig.savefig('bar_charts.png')
        return send_file('bar_charts.png', mimetype='image/png')
    except Exception as e:
        print(e)
        error = 'Something went wrong when trying to create bar charts. Please ensure that you request weather data before attempting to generate the plots.'
        return error
    