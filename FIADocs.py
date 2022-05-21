# -*- coding: utf-8 -*-
# !/usr/bin/python3

# python3 -m pip install yagmail beautifulsoup4 html5lib tweepy pdf2image pytz --no-cache-dir
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
from bs4 import BeautifulSoup


def get911(key):
    with open('/home/pi/.911') as f:
        data = json.load(f)
    return data[key]


EMAIL_USER = get911('EMAIL_USER')
EMAIL_APPPW = get911('EMAIL_APPPW')
EMAIL_RECEIVER = get911('EMAIL_RECEIVER')


def getLastTweetedPost(championship):
    try:
        LOG_FILE = os.path.join(os.path.join(os.path.dirname(os.path.abspath(__file__)), "log_" + championship + ".json"))
        with open(LOG_FILE) as inFile:
            data = json.load(inFile)[0]
        return data["date"], data["title"], data["href"]
    except Exception:
        return "", "", ""


def getPosts(championship):
    # Get last tweeted post date and title
    lastDate, lastTitle, lastHref = getLastTweetedPost(championship)

    # Get Documents Page
    url = ""
    if championship == "F1":
        url = "https://www.fia.com/documents/championships/fia-formula-one-world-championship-14"
        soup = BeautifulSoup(requests.get(url, headers={"Cache-Control": "no-cache", "Pragma": "no-cache"}).text, 'html5lib')
        url = soup.find("select", {"id": "facetapi_select_facet_form_2"}).find_all("option")[-1].get("value")
    elif championship == "F2":
        url = "https://www.fia.com/documents/championships/championships/formula-2-championship-44"
        soup = BeautifulSoup(requests.get(url, headers={"Cache-Control": "no-cache", "Pragma": "no-cache"}).text, 'html5lib')
        url = soup.find("select", {"id": "facetapi_select_facet_form_2"}).find_all("option")[-1].get("value")
    elif championship == "F3":
        url = "https://www.fia.com/documents/championships/fia-formula-3-championship-1012"
        soup = BeautifulSoup(requests.get(url, headers={"Cache-Control": "no-cache", "Pragma": "no-cache"}).text, 'html5lib')
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
        if postDate == lastDate and postTitle == lastTitle and postHref == lastHref:
            break

        # Add to new posts
        newPosts.append({"date": postDate, "title": postTitle, "href": postHref})

    return eventTitle, newPosts


def getScreenshots(pdfHref):
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
    hashtags = ""

    try:
        with open(HASHTAGS_FILE) as inFile:
            hashtags = json.load(inFile)[eventTitle]
    except Exception as ex:
        print("Failed to get Race hashtags")
        yagmail.SMTP(EMAIL_USER, EMAIL_APPPW).send(EMAIL_RECEIVER, "Failed to get Race hashtags - " + os.path.basename(__file__), str(ex) + "\n\n" + eventTitle)

    return hashtags


def getTwitterApi(championship):
    CONSUMER_KEY = ""
    CONSUMER_SECRET = ""
    ACCESS_TOKEN = ""
    ACCESS_TOKEN_SECRET = ""

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

    auth = tweepy.OAuthHandler(CONSUMER_KEY, CONSUMER_SECRET)
    auth.set_access_token(ACCESS_TOKEN, ACCESS_TOKEN_SECRET)
    api = tweepy.API(auth)
    return api


def tweet(tweetStr, hasPics, championship):
    try:
        api = getTwitterApi(championship)
        media_ids = []
        if hasPics:
            imageFiles = sorted([file for file in os.listdir(tmpFolder) if file.split(".")[-1] == "jpg"])
            media_ids = [api.media_upload(os.path.join(tmpFolder, image)).media_id_string for image in imageFiles]

        api.update_status(status=tweetStr, media_ids=media_ids)
        print("Tweeted")
    except Exception as ex:
        print("Failed to Tweet")
        print(ex)
        yagmail.SMTP(EMAIL_USER, EMAIL_APPPW).send(EMAIL_RECEIVER, "Failed to Tweet - " + championship + " - " + os.path.basename(__file__), str(ex) + "\n\n" + tweetStr)


def main():
    for championship in ["F1", "F2", "F3"]:
        print("Championship: " + championship)

        # Get latest posts
        eventTitle, newPosts = getPosts(championship)
        newPosts = list(reversed(newPosts))

        # Set hashtags
        hashtags = getRaceHashtags(eventTitle)
        if championship == "F1":
            hashtags += " " + "#Formula1 #F1"
        elif championship == "F2":
            hashtags += " " + "#Formula2 #F2"
        elif championship == "F3":
            hashtags += " " + "#Formula3 #F3"
        hashtags += " " + "#FIA #GrandPrix"
        hashtags = hashtags.strip()

        # Go through each new post
        for post in newPosts:
            # Get post info
            postTitle, postDate, postHref = post["title"], post["date"], post["href"]
            print(postTitle)
            print(postDate)

            # Screenshot DPF
            hasPics = getScreenshots(postHref)

            # Tweet!
            if championship == "F1":
                postTitle = "NEW F1 DOC" + "\n\n" + postTitle
            elif championship == "F2":
                postTitle = "NEW F2 DOC" + "\n\n" + postTitle
            elif championship == "F3":
                postTitle = "NEW F3 DOC" + "\n\n" + postTitle
            tweet(postTitle + "\n\n" + "Published at: " + postDate + "\n\n" + postHref + "\n\n" + hashtags, hasPics, championship)

            # Save log
            LOG_FILE = os.path.join(os.path.join(os.path.dirname(os.path.abspath(__file__)), "log_" + championship + ".json"))
            with open(LOG_FILE) as inFile:
                data = list(reversed(json.load(inFile)))
                data.append(post)
            with open(LOG_FILE, "w") as outFile:
                json.dump(list(reversed(data)), outFile, indent=2)

            print()


if __name__ == "__main__":
    print("----------------------------------------------------")
    print(datetime.datetime.strftime(datetime.datetime.utcnow(), "%Y/%m/%d %H:%M UTC"))

    # Set temp folder
    tmpFolder = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tmp")
    HASHTAGS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "raceHashtags.json")
    ISRUNNING_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "isRunning.tmp")

    # Check if isRunning file exists
    if os.path.exists(ISRUNNING_FILE):
        print("isRunning")
    else:
        # Create isRunning file
        open(ISRUNNING_FILE, "x")

        try:
            main()
        except Exception as ex:
            print(ex)
            yagmail.SMTP(EMAIL_USER, EMAIL_APPPW).send(EMAIL_RECEIVER, "Error - " + os.path.basename(__file__), str(ex))
        finally:
            # Remove isRunning file
            os.remove(ISRUNNING_FILE)
            print("End")
            print("----------------------------------------------------")
