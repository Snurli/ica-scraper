#!/usr/bin/env python3

import logging
import json
import requests
import secrets
import sys
import os
from recipe_scrapers import scrape_me
from dotenv import load_dotenv
from googletrans import Translator

DEBUG_LOG_ENABLED = 0
TRANSLATION_ENABLED = 0

# User info
icaUser = None
icaPassword = None
icaList = None

# ICA interaction
authTick = None
listId = None


def get_user_info():
    global icaUser, icaPassword, icaList

    print("Reading user information")

    try:
        load_dotenv()
        USR = os.getenv('USR')
        PASS = os.getenv('PASS')
        LIST = os.getenv('LIST')
        if DEBUG_LOG_ENABLED:
            print("User: " + USR + "\nPassword: " + PASS + "\nShopping list: " + LIST)
    except:
        print("Couldn't load environment variables!")
        exit(1)

    icaUser = USR         #Username
    icaPassword = PASS    #Password
    icaList = LIST        #Shopping list

    print("Successfully read user information")

def scrape_recipe(url):
    print("Scraping recipe")

    scraper = scrape_me(url, wild_mode=True)
    ingredients = scraper.ingredients()

    f = open("ingredients", "a")

    f.write(scraper.title() + ":\n")
    f.write(url + "\n\n")

    print("Successfully scraped recipe")

    return ingredients

def translate_recipe(ingredients):
    print("Translating ingredients")

    translator = Translator()

    ingredients_translated = []
    for ingredient in ingredients:
        ingredients_translated.append(translator.translate(ingredient, src='en', dest='sv').text)

    if DEBUG_LOG_ENABLED:
        print(ingredients)
        print(ingredients_translated)

    print("Successfully translated ingredients")
    return ingredients_translated

def ica_login():
    global icaUser, icaPassword, authTick

    print("Logging in")

    # Authentication
    url = "https://handla.api.ica.se/api/login"
    req = requests.get(url, auth=(icaUser, icaPassword))

    if req.status_code != requests.codes.ok:
        print("API request returned error - " + str(req.status_code))
        exit(1)

    if DEBUG_LOG_ENABLED:
        print("Login response: " + req.text)

    print("Successfully logged in")

    # Save authentication ticket
    authTick = req.headers["AuthenticationTicket"]

def ica_get_shopping_lists():
    global authTick

    print("Requesting shopping lists")

    # Setup request
    url = 'https://handla.api.ica.se/api/user/offlineshoppinglists'
    headers = {"Content-Type": "application/json", "AuthenticationTicket": authTick}
    req = requests.get(url, headers=headers)
    response = json.loads(req.content)

    if req.status_code != requests.codes.ok:
        print("API request returned error - " + str(req.status_code))
        exit(1)

    print("Received shopping lists")

    return response['ShoppingLists']

def get_list_id(shopping_lists):
    global icaList

    print("Searching for user shopping list (" + icaList + ") in ICA lists")

    # Find list if it already exists
    for lists in shopping_lists:
        if lists["Title"] == icaList:
            print("Shopping list found!")
            return lists["OfflineId"]

    # Return none if no list is found
    print("Shopping list not found!")
    return None

def ica_create_shopping_list():
    global authTick, icaList, listId

    print("Creating shopping list")

    # Create new list
    newOfflineId = secrets.token_hex(4) + "-" + secrets.token_hex(2) + "-" + secrets.token_hex(2) + "-"
    newOfflineId = newOfflineId + secrets.token_hex(2) + "-" + secrets.token_hex(6)

    # Setup request
    data = json.dumps({"OfflineId": newOfflineId, "Title": icaList, "SortingStore": 0})
    url = 'https://handla.api.ica.se/api/user/offlineshoppinglists'
    headers = {"Content-Type": "application/json", "AuthenticationTicket": authTick}
    req = requests.post(url, headers=headers, data=data)

    # Failed
    if req.status_code != 200:
        print('Failed to create list')
        exit(1)

    # Now get shopping list id
    print('Successfully created list')

    print('Verifying that list is created')

    shopping_lists = ica_get_shopping_lists()
    listId = get_list_id(shopping_lists)

    if listId == None:
        print("Failed to create list!")
        exit(1)

    print(icaList + " created with offlineId " + listId)

def ica_post_products(scraped_products):
    global authTick, listId

    print("Sending ingredients to ICA")

    products = [{"ProductName": i } for i in scraped_products]

    if DEBUG_LOG_ENABLED:
        print(products)

    items = json.dumps({"CreatedRows":products})
    url = "https://handla.api.ica.se/api/user/offlineshoppinglists/" + listId + "/sync"
    headers = {"Content-Type": "application/json", "AuthenticationTicket": authTick}
    req = requests.post(url, headers=headers, data=items)

    if req.status_code != requests.codes.ok:
        print("API request returned error: " + str(req.status_code))
        exit(1)

    print("Successfully sent ingredients")

    if DEBUG_LOG_ENABLED:
        print("Resp: " + req.text)

if len(sys.argv) != 2:
    print('Please enter recipe link')
    exit(1)

# Get username, password and shopping list name
get_user_info()

# Perform scraping
scraped_products = scrape_recipe(sys.argv[1])

if TRANSLATION_ENABLED:
    scraped_products = translate_recipe(scraped_products)

# Login and get auth ticket
ica_login()

# Get lists from ICA
shopping_lists = ica_get_shopping_lists()

# Find matching user list in ICA lists
listId = get_list_id(shopping_lists)

# Create list if it doesn't exist
if listId == None:
    ica_create_shopping_list()

# Post ingredients
ica_post_products(scraped_products)
