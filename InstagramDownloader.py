# coding utf-8
from pprint import pprint
import argparse
import re
import requests
from os import listdir, mkdir
import json
import time
from typing import List
from random import randint


class User():
    def __init__(self, username: str):
        self.username = username
        self.profile_url = f"https://www.instagram.com/{username}"
        self.source_code = self.get_source_code()
        self.dict = self.get_dict()
        self.full_name = self.get_full_name()
        self.profile_picture_url = self.get_profile_picture_url()
        self.biography = self.get_profile_bio()
        self.followers = self.get_followers_count()
        self.followees = self.get_followees_count()
        self.id = self.get_id()
        self.last_posts = self.get_posts()
        self.posts = self.last_posts
        self.post_count: int
        self.page_info: dict

    def get_source_code(self) -> str:
        source = requests.get(self.profile_url)
        if source.status_code == 200:
            return source.text
        else:
            return "error"

    def get_dict(self) -> dict:
        reg_ex = '\"user\":{(.*),\"edge_felix_video_timeline\"'
        match = re.findall(reg_ex, self.source_code)[0]
        user_dict = json.loads("{" + match + "}")
        return user_dict

    def get_profile_picture_url(self) -> str:
        user = self.dict
        pic_url_encoded = user["profile_pic_url"]
        pic_url_decoded = pic_url_encoded.encode().decode('unicode_escape')
        return pic_url_decoded

    def get_profile_bio(self) -> str:
        biography = self.dict["biography"]
        return biography

    def get_followers_count(self) -> int:
        count = self.dict["edge_followed_by"]["count"]
        return count

    def get_followees_count(self) -> int:
        count = self.dict["edge_follow"]["count"]
        return count

    def get_full_name(self) -> str:
        full_name = self.dict["full_name"]
        return full_name

    def get_id(self) -> str:
        return self.dict["id"]

    def get_posts(self):
        regex = "\"edge_owner_to_timeline_media\":(\{.*\}),\"edge_saved_media\""
        match = re.findall(regex, self.source_code)[0]
        data = json.loads(match)
        self.post_count = data["count"]
        self.page_info = data["page_info"]
        post_list = data["edges"]
        return [Post(post) for post in post_list]

    def get_next_page(self):
        """Fetches next 12 and append it to `self.posts`"""
        if self.page_info["has_next_page"]:
            url = "https://www.instagram.com/graphql/query/"
            payload = {
                # as it seems, query_hash is always the same
                # for this kind of query 
                "query_hash": "bfa387b2992c3a52dcbe447467b4b771",  # hardcoded
                "id": self.id,
                "first": 12,
                "after": self.page_info["end_cursor"]
            }
            response = requests.get(url, params=payload)
            if response.status_code == 200:
                data = response.json()["data"]
                user = data["user"]
                timeline = user["edge_owner_to_timeline_media"]
                self.page_info = timeline["page_info"]
                edges = timeline["edges"]
                new_posts = [Post(post) for post in edges]
                self.posts += new_posts
                return new_posts

    def save_profile_picture(self):
        check_output(self.username)
        encoded = self.profile_picture_url.encode()
        decoded = encoded.decode("unicode_escape")
        image = requests.get(decoded).content
        file = open(f"./{self.username}/profile_pic.jpg", 'wb')
        file.write(image)
        file.close()

    def save_user_data(self):
        check_output(self.username)
        data = {
            "id": self.id,
            "username": self.username,
            "full_name": self.full_name,
            "followers": self.followers,
            "followees": self.followees,
            "biography": self.biography
        }
        txt_file = open(
            file=f"./{self.username}/description.json",
            mode='w+',
            encoding="utf8"
        )
        txt_file.write(json.dumps(data))
        txt_file.close()

    def save_posts(self):
        for post in self.posts:
            post.save_post()
            time.sleep(1)

class Post():
    def __init__(self, post_dict: dict):
        self.data = post_dict["node"]
        self.type = self.get_type()
        self.id = self.get_id()
        self.owner = self.get_owner()
        self.caption = self.get_caption()
        self.creation_time = self.get_creation_time()
        self.basename = self.get_basename()
        self.thumbnail = self.get_thumbnail()
        self.media = self.get_media_url()

    def get_type(self) -> str:
        return self.data["__typename"]

    def get_id(self) -> str:
        return self.data["id"]

    def get_owner(self) -> dict:
        return self.data["owner"]

    def get_caption(self) -> str:
        try:
            edges = self.data["edge_media_to_caption"]["edges"]
            node = edges[0]["node"]
            text = node["text"]
            return text
        except:
            return ""

    def get_creation_time(self) -> dict:
        timestamp = self.data["taken_at_timestamp"]
        time_string = time.ctime(timestamp)
        return {
            "timestamp": timestamp,
            "extended": time_string
        }

    def get_basename(self):
        timestamp = self.creation_time["timestamp"]
        time_constructor = time.localtime(timestamp)
        basename = time.strftime("%Y-%m-%d_%X", time_constructor)
        formated_basename = basename.replace(":", "-")
        return formated_basename

    def get_media_url(self) -> list:
        media = []
        if self.type == "GraphImage":
            image_url = self.data["display_url"]
            media.append(image_url)

        elif self.type == "GraphVideo":
            video_url = self.data["video_url"]
            media.append(video_url)

        elif self.type == "GraphSidecar":
            resources = self.data["edge_sidecar_to_children"]
            edges = resources["edges"]
            for item in edges:
                node = item["node"]
                if node["__typename"] == "GraphImage":
                    image_url = node["display_url"]
                    media.append(image_url)
                elif node["__typename"] == "GraphVideo":
                    video_url = node["video_url"]
                    thumbnail = node["display_url"]
                    media.append(video_url)
                    media.append(thumbnail)
        return media

    def get_thumbnail(self) -> str:
        thumbnail = self.data["thumbnail_resources"][-1]
        return thumbnail["src"]

    def save_post(self):
        username = self.owner['username']
        basename = self.basename
        check_output(username)
        path = f"./{username}/{basename}"
        for index, url in enumerate(self.media):
            content = download_media(url)
            extension = get_ext(url)
            filename = f"{path}_{index}{extension}"
            with open(filename, 'wb+') as file:
                file.write(content)
        with open(f'{path}.txt', "w+", encoding='utf8') as txt:
            txt.write(self.caption)

        with open(f'{path}.json', 'w+', encoding='utf-8') as file:
            file.write(json.dumps(self.data))


class Media():
    def __init__(self, node):
        self.node = node
        self.type = self.get_type()

    def get_type(self) -> str:
        return self.node["__typename"]

    def get_media(self):
        pass


def download_media(url: str) -> bytes:
    encoded = url.encode()
    decoded = encoded.decode("unicode_escape")
    content = requests.get(decoded).content
    return content


def save_media(basename):
    pass


def get_ext(url):
    regex = r'(\.[\d\w]+?)\?'
    ext = re.findall(regex, url)[0]
    return ext


def check_output(username):
    """Asserts output folder's existence"""
    if username not in listdir('.'):
        mkdir(f"{username}")
