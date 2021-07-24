import re
import os
from modules.module import Module, Response
import csv
import requests

csv_url = (
    "https://docs.google.com/spreadsheets/d/1PwWbWZ6FPqAgZWOoOcXM8N_tUCuxpEyMbN1NYYC02aM/export?format=csv"
)


class ANSearch(Module):
    """
    A module that searches the Alignment Newsletter for relevant papers/articles etc.
    """

    def __init__(self):
        super().__init__()
        noun_regex = r"""([Pp]aper|[Aa]rticle|([Bb]log)? ?[Pp]ost|[Nn]ewsletter)s?"""
        self.re_search = re.compile(
            r"""((([Ww]hich|[Ww]hat) """
            + noun_regex
            + """ (is|was) (it|that))|"""
            + """([Ii]n )?([Ww]hich|[Ww]hat)('?s| is| was| are| were)? ?(it|that|the|they|those)? ?"""
            + noun_regex
            + """ ?(where|in which|which)?|"""
            + noun_regex
            + """ [Ss]earch) (?P<query>.+)"""
        )
        self.items = []
        self.load_items()

    class Item:
        def __init__(self, row):
            self.row = row

            self.score = 0

        def __repr__(self):
            return '<Item: %f "%s">' % (self.score, self.row)

        def __str__(self):
            return self.__repr__()

    def load_items(self):
        # TODO - Any kind of error checking and handling
        response = requests.get(csv_url)

        csv_reader = csv.reader(response.content.decode().splitlines())

        for row in csv_reader:
            print(row)
            item = self.Item(row=row)
            self.items.append(item)

    # def load_videos(self):
    #     with os.scandir(self.subsdir) as entries:
    #         for entry in entries:
    #             if entry.name.endswith(".en.vtt"):
    #                 vtt_groups = re.match(r"^(.+?)-([a-zA-Z0-9\-_]{11})\.en(-GB)?\.vtt$", entry.name)
    #                 title = vtt_groups.group(1)
    #                 stub = vtt_groups.group(2)
    #
    #                 text = self.process_vtt_file(entry.path)
    #
    #                 description_filename = title + "-" + stub + ".description"
    #                 description_filepath = os.path.join(self.subsdir, description_filename)
    #                 if os.path.exists(description_filepath):
    #                     description = open(description_filepath, encoding="utf8").read()
    #                 else:
    #                     description = ""
    #
    #                 video = self.Video(title, stub, text, description)
    #                 self.videos.append(video)

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
            paper article blog blogpost book
            talking talks rob robert""".split()
        boring_words = [w.strip() for w in boring_words]

        keywords = query.lower().split()
        keywords = [w.strip("\"'?.,!") for w in keywords if w not in boring_words]
        return keywords

    def sort_by_relevance(self, items, search_string, reverse=False):
        keywords = self.extract_keywords(search_string)
        print('Keywords:, "%s"' % keywords)

        for item in items:
            item.score = 0
            for keyword in keywords:
                keyword = keyword.lower()
                for field in item.row:
                    item.score += 1.0 * field.lower().count(keyword) / (len(field) + 1)

                # item.score += 3.0 * item.title.lower().count(keyword) / (len(item.title) + 1)
                # item.score += 1.0 * item.description.lower().count(keyword) / (len(item.description) + 1)
                # item.score += 1.0 * item.text.lower().count(keyword) / (len(item.text) + 1)
        return sorted(items, key=(lambda v: v.score), reverse=reverse)

    def search(self, query):
        result = self.sort_by_relevance(self.items, query, reverse=True)
        print("Search Result:", result)

        best_score = result[0].score
        if best_score == 0:
            return []

        matches = [result[0]]

        for r in result[1:10]:
            if r.score > 0:
                print(r)
            if r.score > (best_score / 2.0):
                matches.append(r)
        return matches

    def process_message(self, message, client=None):
        if self.is_at_me(message):
            text = self.is_at_me(message)

            m = re.match(self.re_search, text)
            if m:
                query = m.group("query")
                return Response(confidence=9, callback=self.process_search_request, args=[query])

        # This is either not at me, or not something we can handle
        return Response()

    @staticmethod
    def list_relevant_items(result):
        item = result[0]
        item_description = "`%s`" % item.row

        reply = "This seems relevant:\n" + item_description

        # if len(result) > 1:
        #     reply += "\nIt could also be:\n"
        #     for item in result[1:5]:
        #         reply += "- `%s`" % item.row

        if len(reply) >= 2000:
            reply = reply[:1995] + "...`"

        return reply

    async def process_search_request(self, query):
        print('Newsletter Query is:, "%s"' % query)
        result = self.search(query)
        if result:
            print("Result:", result)
            return Response(
                confidence=10,
                text=self.list_relevant_items(result),
                why="I looked in the Alignment Newsletter Database and that's what I could find",
            )
        else:
            return Response(
                confidence=8,
                text="No matches found",
                why="I couldn't find anything relevant in the Alignment Newsletter",
            )

    def __str__(self):
        return "Alignment Newsletter Search"
