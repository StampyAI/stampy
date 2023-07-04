"""
Searches the titles, descriptions and transcripts of Rob Miles videos, to find keywords/phrases
"""

import re
import os
from modules.module import Module, Response
from config import subs_dir


class VideoSearch(Module):
    """
    A module that searches the titles, descriptions and transcripts of videos, to find keywords/phrases
    """

    NOT_FOUND_MESSAGE = "No matches found"

    def __init__(self):
        super().__init__()
        self.re_search = re.compile(
            r"""((([Ww]hich|[Ww]hat) vid(eo)? (is|was) (it|that))|
?([Ii]n )?([Ww]hich|[Ww]hat)('?s| is| was| are| were)? ?(it|that|the|they|those)? ?vid(eo)?s? ?(where|in which|which)?|
?[Vv]id(eo)? ?[Ss]earch) (?P<query>.+)"""
        )
        self.subsdir = subs_dir
        self.videos = []
        self.load_videos()

    class Video:
        def __init__(self, title, stub, text="", description=""):

            self.title = title
            self.stub = stub
            self.text = text
            self.description = description

            self.url = "http://youtu.be/%s" % self.stub

            self.score = 0

        def __repr__(self):
            return '<Video %s: %f "%s">' % (self.stub, self.score, self.title)

        def __str__(self):
            return self.__repr__()

    @staticmethod
    def process_vtt_file(vtt_file_name):
        with open(vtt_file_name) as vtt_file:
            lines = []
            for line in vtt_file.readlines():
                regex_matches = re.search(r"<[^>]*>", line)
                if regex_matches:
                    # the timestamp for the start of the line
                    timestamp = regex_matches.group(0)

                    # remove the brackets, leading zeros, and milliseconds
                    # 00:10:17.630 becomes 10:17
                    timestamp = timestamp.lstrip("0<>").lstrip(":").partition(".")[0]

                    # strip out all the html tags from the line
                    pline = re.sub(r"<[^>]*>", "", line.strip())
                    lines.append(timestamp + "|" + pline)
        return "\n".join(lines)

    def load_videos(self):
        with os.scandir(self.subsdir) as entries:
            for entry in entries:
                if entry.name.endswith(".en.vtt"):
                    vtt_groups = re.match(r"^(.+?)-([a-zA-Z0-9\-_]{11})\.en(-GB)?\.vtt$", entry.name)
                    title = vtt_groups.group(1)
                    stub = vtt_groups.group(2)

                    text = self.process_vtt_file(entry.path)

                    description_filename = title + "-" + stub + ".description"
                    description_filepath = os.path.join(self.subsdir, description_filename)
                    if os.path.exists(description_filepath):
                        description = open(description_filepath, encoding="utf8").read()
                    else:
                        description = ""

                    video = self.Video(title, stub, text, description)
                    self.videos.append(video)

    @staticmethod
    def extract_keywords(query):
        boring_words = """
            a about all also am an and any as at back be because but 
            by can come could do does did for from get go have he her 
            him his how i if in is into it its just like make me my no 
            not now of on one only or our out over say see she so some 
            take than that the their them then there these they this 
            time to up us use was we what when which who will with would 
            your know find where something name remember video talk talked 
            talking talks rob robert""".split()
        boring_words = [w.strip() for w in boring_words]

        keywords = query.lower().split()
        keywords = [w.strip("\"'?.,!") for w in keywords if w not in boring_words]
        return keywords

    def sort_by_relevance(self, videos, search_string, reverse=False):
        keywords = self.extract_keywords(search_string)
        self.log.info(self.class_name, video_keywords=keywords)

        for video in videos:
            video.score = 0
            for keyword in keywords:
                keyword = keyword.lower()
                video.score += 3.0 * video.title.lower().count(keyword) / (len(video.title) + 1)
                video.score += 1.0 * video.description.lower().count(keyword) / (len(video.description) + 1)
                video.score += 1.0 * video.text.lower().count(keyword) / (len(video.text) + 1)
        return sorted(videos, key=(lambda v: v.score), reverse=reverse)

    def search(self, query):
        result = self.sort_by_relevance(self.videos, query, reverse=True)
        self.log.info(self.class_name, search_result=result)

        best_score = result[0].score
        if best_score == 0:
            return []

        matches = [result[0]]

        for video in result[1:10]:
            if video.score > 0:
                self.log.info(
                    self.class_name, search_result_title=video.title, search_result_score=video.score
                )
            if video.score > (best_score / 2.0):
                matches.append(video)
        return matches

    def process_message(self, message):
        if self.is_at_me(message):
            text = self.is_at_me(message)

            m = re.match(self.re_search, text)
            if m:
                query = m.group("query")
                return Response(confidence=9, callback=self.process_search_request, args=[query])

        # This is either not at me, or not something we can handle
        return Response()

    @staticmethod
    def list_relevant_videos(result):
        video = result[0]
        video_description = '"%s" %s' % (video.title, video.url)

        reply = "This video seems relevant:\n" + video_description

        if len(result) > 1:
            reply += "\nIt could also be:\n"
            for video in result[1:5]:
                reply += '- "%s" <%s>\n' % (video.title, video.url)

        return reply

    async def process_search_request(self, query):
        self.log.info(self.class_name, operation="process_search_request", video_query=query)
        result = self.search(query)
        if result:
            self.log.info(self.class_name, operation="process_search_request", search_resutl=result)
            return Response(
                confidence=10,
                text=self.list_relevant_videos(result),
                why="Those are the videos that seem related!",
            )
        else:
            return Response(
                confidence=8, text=self.NOT_FOUND_MESSAGE, why="I couldn't find any relevant videos"
            )

    def __str__(self):
        return "Video Search Manager"

    @property
    def test_cases(self):
        return [
            self.create_integration_test(
                test_message="Which video did rob play civilization V in?",
                expected_regex="Superintelligence Mod for Civilization V+",
            ),
            self.create_integration_test(
                test_message="which video is trash?", expected_response=self.NOT_FOUND_MESSAGE,
            ),
        ]
