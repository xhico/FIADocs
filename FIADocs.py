# -*- coding: utf-8 -*-
# !/usr/bin/python3

# sudo apt install poppler-utils -y

import json
import os
import datetime
import pytz
import shutil
import urllib.request
import urllib.parse
import requests
import tweepy
import yagmail
import pdf2image
import psutil
from bs4 import BeautifulSoup


def get911(key):
    """
    Given a key, returns the corresponding value from the 911 data file.

    Args:
        key (str): The key to look up in the 911 data file.

    Returns:
        The value associated with the given key in the 911 data file.

    Raises:
        FileNotFoundError: If the 911 data file cannot be found.
        KeyError: If the given key is not present in the 911 data file.
    """
    with open('/home/pi/.911') as f:  # Open the 911 data file.
        data = json.load(f)  # Load the JSON data from the file.
    return data[key]  # Return the value associated with the given key.


def getLog(championship):
    """
    Retrieves the log data for the given championship.

    Args:
        championship (str): The name of the championship.

    Returns:
        A list representing the log data for the given championship.

    Raises:
        None.
    """
    # Determine the log file path for the given championship.
    LOG_FILE = os.path.join(os.path.join(os.path.dirname(os.path.abspath(__file__)), "log_" + championship + ".json"))

    try:
        # Try to open the log file and load the data.
        with open(LOG_FILE) as inFile:
            data = json.load(inFile)
    except Exception:
        # If an error occurs (e.g. file doesn't exist), create a new empty log file and return an empty list.
        data = []
        with open(LOG_FILE, "w") as outFile:
            json.dump(data, outFile, indent=2)

    # Return the log data (either loaded from the file or created as an empty list).
    return data


def getPosts(championship):
    """
    Scrapes the FIA website to retrieve the latest posts related to a championship.

    Args:
    championship (str): The name of the championship to retrieve posts for. Valid values are "F1", "F2", or "F3".

    Returns:
    eventTitle (str): The title of the latest event.
    newPosts (list): A list of dictionaries containing details of new posts since the last time the function was run.
    Each dictionary contains the keys 'date' (string), 'title' (string), and 'href' (string).
    """

    # Get championship log
    log = getLog(championship)

    # Get Documents Page
    url = ""
    if championship == "F1":
        url = "https://www.fia.com/documents/championships/fia-formula-one-world-championship-14"
        soup = BeautifulSoup(requests.get(url).text, 'html5lib')
        url = soup.find("select", {"id": "facetapi_select_facet_form_2"}).find_all("option")[-1].get("value")
    elif championship == "F2":
        url = "https://www.fia.com/documents/championships/championships/formula-2-championship-44"
        soup = BeautifulSoup(requests.get(url).text, 'html5lib')
        url = soup.find("select", {"id": "facetapi_select_facet_form_2"}).find_all("option")[-1].get("value")
    elif championship == "F3":
        url = "https://www.fia.com/documents/championships/fia-formula-3-championship-1012"
        soup = BeautifulSoup(requests.get(url).text, 'html5lib')
        url = soup.find("select", {"id": "facetapi_select_facet_form_2"}).find_all("option")[-1].get("value")

    # Make soup
    soup = BeautifulSoup(requests.get("https://www.fia.com" + url).text, 'html5lib')

    # Get Documents
    documents = soup.find("div", {"class": "decision-document-list"})
    lastEvent = documents.find("ul", {"class": "event-wrapper"})
    eventTitle = lastEvent.find("div", {"class": "event-title"}).text.title()

    # Go through each post
    newPosts = []
    eventDocuments = lastEvent.find("ul", {"class": "document-row-wrapper"})
    for post in eventDocuments.find_all("li", {"class": "document-row"}):
        post = post.find("a")
        postTitle = post.find("div", {"class": "title"}).text.strip()
        postHref = "https://www.fia.com" + urllib.parse.quote(post.get("href"))
        postDate = post.find("div", {"class": "published"}).text.strip().replace("Published on ", "").replace("CET", "").replace(".", " ").strip()

        # Convert datetime to UTC time-zone
        postDate = datetime.datetime.strptime(postDate, "%d %m %y %H:%M").astimezone(pytz.UTC).strftime("%Y/%m/%d %H:%M") + " UTC"

        # Check
        if {"date": postDate, "title": postTitle, "href": postHref} not in log:
            # Add to new posts
            newPosts.append({"date": postDate, "title": postTitle, "href": postHref})

    return eventTitle, newPosts


def getScreenshots(pdfHref):
    """Download a PDF from the given URL, convert its first four pages to JPEG images, and save them to a temporary folder.

    Args:
        pdfHref (str): The URL of the PDF to be downloaded.

    Returns:
        bool: True if the conversion is successful and at least one image is saved, False otherwise.
    """

    try:
        # Reset tmpFolder
        if os.path.exists(tmpFolder):
            shutil.rmtree(tmpFolder)
        os.mkdir(tmpFolder)

        # Download PDF
        pdfFile = os.path.join(tmpFolder, "tmp.pdf")
        urllib.request.urlretrieve(pdfHref, pdfFile)

        # Check what OS
        if os.name == "nt":
            poppler_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "poppler-win\Library\bin")
            pages = pdf2image.convert_from_path(poppler_path=poppler_path, pdf_path=pdfFile)
        else:
            pages = pdf2image.convert_from_path(pdf_path=pdfFile)

        # Save the first four pages
        for idx, page in enumerate(pages[0:4]):
            jpgFile = os.path.join(tmpFolder, "tmp_" + str(idx) + ".jpg")
            page.save(jpgFile)
        hasPics = True
    except Exception:
        print("Failed to screenshot")
        hasPics = False

    return hasPics


def getRaceHashtags(eventTitle):
    """
    This function takes an event title as input and returns a string of hashtags for that event.
    It reads the hashtags data from a JSON file and retrieves the hashtags for the specified event.
    If there is an error reading the file, it sends an error notification email with details.

    Args:
        eventTitle (str): The title of the event for which to retrieve hashtags.

    Returns:
        str: A string of hashtags for the specified event, or an empty string if no hashtags are found.
    """
    hashtags = ""  # initialize hashtags variable as an empty string

    try:
        with open(HASHTAGS_FILE) as inFile:  # open the hashtags file
            hashtags = json.load(inFile)[eventTitle]  # load the data from the file and retrieve the hashtags for the specified event
    except Exception as ex:  # if there is an error reading the file
        print("Failed to get Race hashtags")  # print a message to the console
        yagmail.SMTP(EMAIL_USER, EMAIL_APPPW).send(EMAIL_RECEIVER, "Failed to get Race hashtags - " + os.path.basename(__file__), str(ex) + "\n\n" + eventTitle)  # send an error notification email with details

    return hashtags  # return the string of hashtags, or an empty string if no hashtags were found


def getTwitterApi(championship):
    """
    A function that takes the championship name as an argument and returns a tweepy API object
    authenticated using the appropriate Twitter credentials for that championship.

    Args:
    championship (str): The name of the championship (F1, F2, or F3)

    Returns:
    tweepy.API object: authenticated API object for the appropriate Twitter credentials
    """

    # Twitter API keys and secrets
    CONSUMER_KEY = ""
    CONSUMER_SECRET = ""
    ACCESS_TOKEN = ""
    ACCESS_TOKEN_SECRET = ""

    # Set Twitter API credentials based on the championship name
    if championship == "F1":
        CONSUMER_KEY = get911('TWITTER_F1DOCS_CONSUMER_KEY')
        CONSUMER_SECRET = get911('TWITTER_F1DOCS_CONSUMER_SECRET')
        ACCESS_TOKEN = get911('TWITTER_F1DOCS_ACCESS_TOKEN')
        ACCESS_TOKEN_SECRET = get911('TWITTER_F1DOCS_ACCESS_TOKEN_SECRET')
    elif championship == "F2":
        CONSUMER_KEY = get911('TWITTER_F2DOCS_CONSUMER_KEY')
        CONSUMER_SECRET = get911('TWITTER_F2DOCS_CONSUMER_SECRET')
        ACCESS_TOKEN = get911('TWITTER_F2DOCS_ACCESS_TOKEN')
        ACCESS_TOKEN_SECRET = get911('TWITTER_F2DOCS_ACCESS_TOKEN_SECRET')
    elif championship == "F3":
        CONSUMER_KEY = get911('TWITTER_F3DOCS_CONSUMER_KEY')
        CONSUMER_SECRET = get911('TWITTER_F3DOCS_CONSUMER_SECRET')
        ACCESS_TOKEN = get911('TWITTER_F3DOCS_ACCESS_TOKEN')
        ACCESS_TOKEN_SECRET = get911('TWITTER_F3DOCS_ACCESS_TOKEN_SECRET')

    # Authenticate and return the API object
    auth = tweepy.OAuthHandler(CONSUMER_KEY, CONSUMER_SECRET)
    auth.set_access_token(ACCESS_TOKEN, ACCESS_TOKEN_SECRET)
    api = tweepy.API(auth)
    return api


def tweet(tweetStr: str, hasPics: bool, championship: str) -> None:
    """
    Posts a tweet with optional pictures to Twitter.

    Parameters:
        tweetStr (str): The text of the tweet.
        hasPics (bool): Whether or not the tweet has pictures.
        championship (str): The name of the championship.

    Returns:
        None
    """

    try:
        # Get the Twitter API object.
        api = getTwitterApi(championship)

        media_ids = []
        if hasPics:
            # Get a list of image files from a temporary folder.
            imageFiles = sorted([file for file in os.listdir(tmpFolder) if file.split(".")[-1] == "jpg"])

            # Upload each image to Twitter and get its media ID.
            media_ids = [api.media_upload(os.path.join(tmpFolder, image)).media_id_string for image in imageFiles]

        # Post the tweet with any attached images.
        api.update_status(status=tweetStr, media_ids=media_ids)

        print("Tweeted")

    except Exception as ex:
        print("Failed to Tweet")
        print(ex)

        # Send an email notification if the tweet fails.
        yagmail.SMTP(EMAIL_USER, EMAIL_APPPW).send(
            EMAIL_RECEIVER,
            "Failed to Tweet - " + championship + " - " + os.path.basename(__file__),
            str(ex) + "\n\n" + tweetStr
        )


def main():
    """
    Main function that loops through each championship and publishes a tweet for each new post found.

    Returns:
    None
    """
    for championship in ["F2"]:  # loop through the championships
        print("Championship: " + championship)

        # Get latest posts
        eventTitle, newPosts = getPosts(championship)  # retrieve the latest posts for the championship
        newPosts = list(reversed(newPosts))  # reverse the order of new posts for easier reading

        # Set hashtags
        hashtags = getRaceHashtags(eventTitle)  # get hashtags for the championship
        if championship == "F1":  # add additional hashtags based on the championship
            hashtags += " " + "#Formula1 #F1"
        elif championship == "F2":
            hashtags += " " + "#Formula2 #F2"
        elif championship == "F3":
            hashtags += " " + "#Formula3 #F3"
        hashtags += " " + "#FIA #GrandPrix"  # add common hashtags
        hashtags = hashtags.strip()  # remove leading and trailing spaces from the hashtag string

        # Go through each new post
        for post in newPosts:
            # Get post info
            postTitle, postDate, postHref = post["title"], post["date"], post["href"]  # retrieve the post details
            print(postTitle)
            print(postDate)

            # Screenshot DPF
            hasPics = getScreenshots(postHref)  # capture a screenshot of the post

            # Tweet!
            if championship == "F1":  # format the post title based on the championship
                postTitle = "NEW F1 DOC" + "\n\n" + postTitle
            elif championship == "F2":
                postTitle = "NEW F2 DOC" + "\n\n" + postTitle
            elif championship == "F3":
                postTitle = "NEW F3 DOC" + "\n\n" + postTitle
            tweet(postTitle + "\n\n" + "Published at: " + postDate + "\n\n" + postHref + "\n\n" + hashtags, hasPics, championship)  # compose and publish the tweet

            # Save log
            LOG_FILE = os.path.join(os.path.join(os.path.dirname(os.path.abspath(__file__)), "log_" + championship + ".json"))  # specify the path of the log file for the championship
            with open(LOG_FILE) as inFile:  # open the log file
                data = list(reversed(json.load(inFile)))  # read the previous log data and reverse the order for easier reading
                data.append(post)  # add the current post to the log
            with open(LOG_FILE, "w") as outFile:  # open the log file for writing
                json.dump(list(reversed(data)), outFile, indent=2)  # write the updated log data in reversed order

            print()  # print a blank line for formatting purposes


if __name__ == "__main__":
    print("----------------------------------------------------")
    print(str(datetime.datetime.now().strftime("%Y/%m/%d %H:%M:%S")))

    # Set temp folder
    tmpFolder = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tmp")
    HASHTAGS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "raceHashtags.json")

    # Set email
    EMAIL_USER = get911('EMAIL_USER')
    EMAIL_APPPW = get911('EMAIL_APPPW')
    EMAIL_RECEIVER = get911('EMAIL_RECEIVER')

    # Check if script is already running
    procs = [proc for proc in psutil.process_iter(attrs=["cmdline"]) if os.path.basename(__file__) in '\t'.join(proc.info["cmdline"])]
    if len(procs) > 2:
        print("isRunning")
    else:
        try:
            main()
        except Exception as ex:
            print(ex)
            yagmail.SMTP(EMAIL_USER, EMAIL_APPPW).send(EMAIL_RECEIVER, "Error - " + os.path.basename(__file__), str(ex))
        finally:
            print("End")
            print("----------------------------------------------------")
