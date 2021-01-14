import pandas as pd
import numpy as np
from sqlalchemy import MetaData, Column, insert, Table
import pymysql
from mysql.connector import errorcode
from sqlalchemy import create_engine
import mysql.connector
from scipy.spatial.distance import jaccard
import plotly.graph_objects as go
import plotly.express as px


def city_review_totals(engine, city):
    '''
    Queries the local database to get review totals by city.
    :param engine: Engine
        A sqlalchemy engine to connect to the DB.
    :param city: str
        Name of the city to be queried.
    :return: DataFrame
        A dataframe containing the totals.
    '''
    # Queries to pull city-specific info from the db.
    query_str1 = 'SELECT business_id, city FROM business WHERE city = "{}"'.format(city)
    query_str2 = 'SELECT business_id, stars FROM review'

    # Reads in to dataframes from the db.
    df_business_city = pd.read_sql(query_str1, engine)
    df_review_stars = pd.read_sql(query_str2, engine)

    # Hashable to check whether a review is from the city.
    city_id_set = set(df_business_city['business_id'])

    # List comprehension to keep only reviews from the city. Note, vectorization is not possible because
    # Series are not hashable (Not sure if there is a workaround).
    city_business = [(row[0], row[1]) for row in df_review_stars.itertuples(index=False) if row[0] in city_id_set]

    # Form into dataframe and count value totals
    df_city_reviews = pd.DataFrame(city_business, columns=['business_id', 'stars'])
    df_review_totals = df_city_reviews['stars'].value_counts().to_frame().reset_index().rename(
    columns={'index': 'stars', 'stars': 'total_count'}).sort_values('stars', axis=0)

    return df_review_totals


def top_ten_tag(tag, engine):
    '''
    Retrieves the total counts for a given category tag in all cities and plots the top 10.
    :param tag: str
        The tag to search for.
    :param engine: Engine
        sqlalchemy engine to query DB
    :return: DataFrame
        Dataframe containing the full list of cities with tag totals.
    '''
    query1 = 'SELECT * FROM category_ref WHERE LOWER(category_name) LIKE "{}"'.format(tag)
    df_tag = pd.read_sql(query1, engine)

    if len(df_tag['category_id']) == 0:
        raise ValueError('There are no matching tags')
        return

    tag_id = df_tag['category_id'][0]

    # Query to retrieve totals for given tag from all cities.
    query2 = (  'SELECT b.city, '
                'COUNT(city) as cnt '
                'FROM business b '
                'INNER JOIN business_category bc '
                'ON bc.business_id=b.business_id WHERE category_id={} '
                'GROUP BY b.city '
                'ORDER BY cnt DESC '
                'LIMIT 10; '.format(tag_id)
    )

    # Retrieve the data
    df_totals = pd.read_sql(query2, engine)
    return df_totals

def get_top_jaccard(city, engine):
    '''
    Retrieves the top 5 Jaccard Similarity scores for businesses in the given city,
    in relation to the various business attributes and the 'is_open' value.
    :param city: str
    :param engine: Engine
        sqlalchemy engine to query db
    :return: dict
    '''

    # Queries the db for all businesses in the city and their attribute tags.
    query = (
        'SELECT '
        'b.is_open, '
        'ba.* '
        'FROM business b '
        'INNER JOIN business_attributes ba '
        'ON ba.business_id = b.business_id '
        'WHERE b.city = "{}";'.format(city)
    )

    # Reads into df and drops to numpy
    df = pd.read_sql(query, engine)
    df.drop(columns='businessAcceptsBitcoin', inplace=True)
    mat = df.to_numpy()[:, np.r_[0, 2:18]]

    # Reserves the 'is_open' value.
    open_vec = mat[:, 0]

    # Iterates over the columns of the attributes and calculates Jaccard similarity
    # to the is_open column. Sorts top 5 and returns in format for plotly bar graph.
    jacc_scores = 1 - np.asarray([jaccard(open_vec, mat[:, j]) for j in range(17)])
    attr_names = np.asarray((df.columns)[2:])
    idx = np.argsort(jacc_scores)[::-1]
    jacc_sorted = jacc_scores[idx][0:5]
    attr_sorted = attr_names[idx][0:5]
    dict = {'Top 5 tags for open businesses': list(attr_sorted), 'Jaccard Similarity': list(jacc_sorted)}
    return dict

def geo_query(city,tag, engine):
    '''
    Queries DB for geospatial data
    :param city: str
        City to query.
    :param tag: str
        The filtering tag
    :param engine: engine
        sqlalchemy/pymsql engine for the connection.
    :return: DataFrame, float, float
    '''

    query1 = 'SELECT * FROM category_ref WHERE LOWER(category_name) LIKE "{}"'.format(tag)
    df_tag = pd.read_sql(query1, engine)
    tag_id = df_tag['category_id'][0]
    # Get the business coordinates for open business in given city
    query2 = (
        'SELECT '
        'b.name, '
        'b.latitude, '
        'b.longitude, '
        'b.stars '
        'FROM business b '
        'INNER JOIN business_category bc '
        'ON bc.business_id=b.business_id WHERE category_id={} '
        'AND city = "{}" AND is_open = 1 ;'.format(tag_id, city)
    )

    # Read into df
    df = pd.read_sql(query2, engine)
    x_max = df['latitude'].max()
    x_min = df['latitude'].min()
    y_max = df['longitude'].max()
    y_min = df['longitude'].min()
    x_cent = x_min + (x_max - x_min)/2
    y_cent = y_min + (y_max - y_min)/2
    return df, x_cent, y_cent

def get_geoscatter(df, x_cent, y_cent, token):
    '''
    Creates a geoscatter figure from the mapbox library.
    :param df: DataFrame
        Contains longitude, latitude, stars, and name of each business.
    :param x_cent: x centerpoint for the map
    :param y_cent: y center point.
    :param token: Mapbox access token
    :return: figure
    '''
    fig = go.Figure(
        go.Scattermapbox(
            lat=df['latitude'],
            lon=df['longitude'],
            mode='markers',
            # Note the mouseover text needs to be put into the format of a single string or
            # iterable of strings.
            text=[df['name'][i] + '<br>' + str(df['stars'][i]) + ' stars' for i in range(df.shape[0])],
            hoverinfo='text',
            marker=go.scattermapbox.Marker(
                size=(df['stars']**2),
                color=df['stars'],
                colorscale='Bluered'
            )
        ),
        layout=dict(title={'text': 'Filtered Businesses. Larger/Redder Means Higher Average Stars'}, font_family='Garamond', font_size = 18),
    )

    fig.update_layout(
        hovermode='closest',
        paper_bgcolor = "#DCDCDC",
        plot_bgcolor='#E9E9E9',
        mapbox=dict(
            accesstoken=token,
            bearing=0,
            center=go.layout.mapbox.Center(
                lat=x_cent,
                lon=y_cent
            ),
            style = 'streets',
            pitch=0,
            zoom=10
        )
    )
    return fig

# Function to create a bar figure to be fed to 'topfive-jaccard'
def create_bar(dct):
    '''
    Creates a bar graph from a dict.
    :param dict: dict
        Format is {x: [data], y:[data]}
    :return: figure
    '''
    if dct == None:
        fig = px.bar({}, x=[], y=[])
    else:
        fig = px.bar(dct, x='Top 5 tags for open businesses', y='Jaccard Similarity', color='Top 5 tags for open businesses',
                     color_discrete_sequence=px.colors.sequential.Blugrn, barmode="relative",
                     title = 'Top 5 attributes associated with being open (Jaccard Similarity)')
        fig.update_layout(
            font_family = 'Garamond',
            font_size=18,
            bargap=0.5
        )
        fig.layout.paper_bgcolor = "#DCDCDC"
        fig.layout.plot_bgcolor = '#E9E9E9'

    return fig

def get_heatmap(city, tag, engine, token):
    query1 = 'SELECT * FROM category_ref WHERE LOWER(category_name) LIKE "{}"'.format(tag)
    df_tag = pd.read_sql(query1, engine)
    tag_id = df_tag['category_id'][0]
    # Get the business coordinates for open business in given city
    query2 = (
        'SELECT '
        'b.name, '
        'b.latitude, '
        'b.longitude, '
        'b.review_count '
        'FROM business b '
        'INNER JOIN business_category bc '
        'ON bc.business_id=b.business_id WHERE category_id={} '
        'AND city = "{}" AND is_open = 1 ;'.format(tag_id, city)
    )

    # Read into df
    df = pd.read_sql(query2, engine)
    x_max = df['latitude'].max()
    x_min = df['latitude'].min()
    y_max = df['longitude'].max()
    y_min = df['longitude'].min()
    x_cent = x_min + (x_max - x_min) / 2
    y_cent = y_min + (y_max - y_min) / 2

    max_cnt = df['review_count'].max()

    px.set_mapbox_access_token(token)
    fig = px.density_mapbox(df, lat='latitude', lon='longitude', z='review_count', radius=40,
                            center=dict(lat=x_cent, lon=y_cent), zoom=10,
                            mapbox_style="streets", range_color=[0, max_cnt], title = "Review Density in {}".format(city))
    fig.update_layout(
        font_family='Garamond',
        font_size=18,
        title_x = 0.5
    )
    fig.layout.paper_bgcolor = "#DCDCDC"
    fig.layout.plot_bgcolor = '#E9E9E9'

    return fig

def get_monthmap(city, tag, engine, token):
    query1 = 'SELECT * FROM category_ref WHERE LOWER(category_name) LIKE "{}"'.format(tag)
    df_tag = pd.read_sql(query1, engine)
    tag_id = df_tag['category_id'][0]
    # Get the business coordinates for open business in given city
    query2 = (
        'SELECT '
        'MONTH(r.date) AS mnths, '
        'COUNT(MONTH(r.date)) AS cnt '
        'FROM business b '
        'INNER JOIN review r '
        'ON r.business_id=b.business_id '
        'INNER JOIN business_category bc '
        'ON bc.business_id = r.business_id '
        'WHERE b.city = "{}" AND bc.category_id = {} '
        'GROUP BY mnths '
        'ORDER BY mnths ASC'.format(city, tag_id)
    )

    # Read into df
    df = pd.read_sql(query2, engine)

    # Dict to change from keys to months
    monthkey = {1:'Jan', 2:'Feb', 3:'Mar', 4:'Apr', 5:'May', 6:'Jun', 7:'Jul', 8:'Aug', 9:'Sep', 10:'Oct', 11:'Nov', 12:'Dec'}

    # Holder DF in case there are months with no reviews. Merge to keep everything
    # and have empty months in the graph.
    dff = pd.DataFrame(monthkey.items(), columns=['mnths', 'str_mnths'])
    df_final = dff.merge(df, on='mnths', how='left')


    fig = px.bar(df_final, x='str_mnths', y='cnt', color='str_mnths', barmode="relative",
                 color_discrete_sequence=px.colors.sequential.Blugrn,
                 title = 'Seasonality by Review Counts', labels={'str_mnths':'Month', 'cnt':'Review Count'})
    fig.update_layout(
        font_family = 'Garamond',
        font_size=18,
        title_x=0.5
    )
    fig.update_traces(showlegend=False)
    fig.layout.paper_bgcolor = "#DCDCDC"
    fig.layout.plot_bgcolor = '#E9E9E9'

    return fig