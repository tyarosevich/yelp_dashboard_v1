import pandas as pd
import dash
import dash_core_components as dcc
import dash_html_components as html
import plotly.express as px
from dash.dependencies import Input, Output
import utils
from sqlalchemy import MetaData, Column, insert, Table
import pymysql
from mysql.connector import errorcode
from sqlalchemy import create_engine
import mysql.connector
import os
import configparser
import plotly.graph_objects as go


# Holder df for initial display
df = pd.read_csv('static/test_df.csv')
df_drop = pd.read_csv('static/drop_list.csv', names=['category_name', 'category_id'])
cat_names = df_drop['category_name']

# Login info for my local MySQL db, stored in a .env file.
user_login = os.environ['DB_LOGIN']
pword_login = os.environ['DB_PWORD']
mapbox_token = os.environ['MAPBOX_TOKEN']

# user_login = 'admin'
# pword_login = 'Exodu$18'
# mapbox_token = 'pk.eyJ1IjoidHlhcm9zZXZpY2giLCJhIjoiY2tqbHlsejF3MDRwbzJ5bXVxY2d5cDlsbyJ9.zBWyx6rzTIo6Uw_w1Iu-AA'

# Creates a sqlalchmy engine for use throughout the project.
engine = create_engine('mysql+pymysql://%s:%s@yelp-db-hosted.ctvsareaeqyr.us-east-2.rds.amazonaws.com/yelp_challengedb' %(user_login, pword_login), pool_recycle=3600, pool_size=5)

external_stylesheets = ['https://codepen.io/chriddyp/pen/bWLwgP.css']

app = dash.Dash(__name__, external_stylesheets=external_stylesheets)
application = app.server
app.title='Locale Scouting With Yelp Data'

app.layout = html.Div(children=[

    html.H1(
        children='Location Scouting With Yelp Data',
        style={
            'textAlign': 'center'
        }),

    # Dropdown to select business tags.
    html.Label('Dropdown'),
    dcc.Dropdown(
        id= 'dropdown',
        options=[{'label': name, 'value': name} for name in cat_names],
        value='Seafood'
    ),

    dcc.Graph(
        id='topten-graph',
    ),


    html.Div(style = {'backgroundColor': "#DCDCDC"}, children = [
        # Layout bar graph for top 5 business attributes by Jaccard similarity.
        dcc.Graph(id='topfive-jaccard', style={'display':'inline-block'}),
        # An overlay of filtered businesses on a mapbox map.
        dcc.Graph(id = 'geograph',style={'display':'inline-block'})
    ]),
    dcc.Graph(id='monthgraph', style={'display':'inline-block'}),
    dcc.Graph(id='heatgraph', style={'display':'inline-block'}),

    # Hidden div inside the app that stores the intermediate value
    html.Div(id='intermediate-value', style={'display': 'none'})

])

# Stores a JSON in the browser containing the top-ten data for
# the tag input from the dropdown menu.
@app.callback(
    Output('intermediate-value', 'children'),
    Input('dropdown', 'value'))
def clean_data(value):
    # some expensive clean data step
    df_tag_totals = utils.top_ten_tag(value, engine)

    # more generally, this line would be
    # json.dumps(cleaned_df)
    return df_tag_totals.to_json(date_format='iso', orient='split')

# Updates a graph displaying the ten cities with the highest count of a given tag.
@app.callback(Output('topten-graph', 'figure'), Input('intermediate-value', 'children'))
def update_graph(jsonified_cleaned_data):

    dff = pd.read_json(jsonified_cleaned_data, orient='split')

    figure = px.bar(dff[0:10], x="city", y="cnt", color="city",color_discrete_sequence=px.colors.sequential.Blugrn, barmode="relative")
    figure.update_layout(bargap=0.75)
    figure.layout.paper_bgcolor = "#DCDCDC"
    figure.layout.plot_bgcolor = '#E9E9E9'
    return figure

# Generates the top 5 attributes most associated with the being_open boolean,
# measured by Jaccard similarity.
@app.callback(Output('topfive-jaccard', 'figure'), [Input('topten-graph', 'hoverData')])
def top5jaccard(hoverData):

    # Grab mouseover city or set initial value.
    if hoverData == None:
        city = 'Toronto'
    else:
        city = hoverData['points'][0]['x']

    # Get a dict of the top 5 tags associated with being open
    # by Jaccard similarity.
    dict = utils.get_top_jaccard(city, engine)
    # Calls helper function to create the figure.
    return utils.create_bar(dict)

# Callback to generate the mapbox figure based on mouseover from the top-ten graph.
@app.callback(Output('geograph', 'figure'), [Input('topten-graph', 'hoverData'), Input('dropdown', 'value')])
def update_geo(hoverData, dropdown):

    tag = dropdown

    # Grab mouseover city/set initial value.
    if hoverData == None:
        city = 'Toronto'
    else:
        city = hoverData['points'][0]['x']

    # Helper function to query the DB/clean/convert data,
    # and calculate box center based on the data.
    df, x, y = utils.geo_query(city, tag, engine)
    # Helper function to generate the geoscatter figure.
    fig = utils.get_geoscatter(df, x, y, mapbox_token)

    return fig


@app.callback(Output('heatgraph', 'figure'), [Input('topten-graph', 'hoverData'), Input('dropdown', 'value')])
def update_heat(hoverData, dropdown):
    tag = dropdown
    # Grab mouseover city/set initial value.
    if hoverData == None:
        city = 'Toronto'
    else:
        city = hoverData['points'][0]['x']
    fig = utils.get_heatmap(city, tag, engine, mapbox_token)

    return fig

@app.callback(Output('monthgraph', 'figure'), [Input('topten-graph', 'hoverData'), Input('dropdown', 'value')])
def update_month(hoverData, dropdown):
    tag = dropdown
    # Grab mouseover city/set initial value.
    if hoverData == None:
        city = 'Toronto'
    else:
        city = hoverData['points'][0]['x']
    fig = utils.get_monthmap(city, tag, engine, mapbox_token)

    return fig



######################
######################
######################
# if __name__ == '__main__':
#     app.run_server(debug=True)

if __name__ == '__main__':
    app.run_server(host = '0.0.0.0', port=8080, debug=True)