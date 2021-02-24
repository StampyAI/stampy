import re
import os
from module import Module


class VideoSearch(Module):
    """
    A module that searches the titles, descriptions and transcripts of videos, to find keywords/phrases
    """

    def __init__(self):
        Module.__init__(self)
        # self.re_search = re.compile(r"""video search (?P<query>\w+)""")
        # self.re_search = re.compile(r"""(([wW]hat( video)?|[wW]hich (video))('s| is| was)? ?(that|the|it)? ?|[Vv]ideo ?[Ss]earch) (?P<query>.+)""")
        self.re_search = re.compile(
            r"""((([Ww]hich|[Ww]hat) vid(eo)? (is|was) (it|that))|
?([Ii]n )?([Ww]hich|[Ww]hat)('?s| is| was| are| were)? ?(it|that|the|they|those)? ?vid(eo)?s? ?(where|in which|which)?|
?[Vv]id(eo)? ?[Ss]earch) (?P<query>.+)"""
        )
        # self.re_nextq = re.compile(r"""(([wW]hat('| i)s|[Cc]an we have|[Ll]et's have|[gG]ive us)?( ?[Aa](nother)?|( the)? ?[nN]ext) question,?( please)?\??|
        # ?([Dd]o you have|([Hh]ave you )?[gG]ot)?( ?[Aa]ny( more| other)?| another) questions?( for us)?\??)!?""")
        self.subsdir = "./subs/"
        self.videos = []
        self.loadvideos()

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

    def processvttfile(self, vttfilename):
        with open(vttfilename) as vttfile:
            lines = []
            for line in vttfile.readlines():
                m = re.search(r"<[^>]*>", line)
                if m:
                    timestamp = m.group(0)  # the timestamp for the start of the line

                    # remove the brackets, leading zeros, and milliseconds
                    # 00:10:17.630 becomes 10:17
                    timestamp = timestamp.lstrip("0<>").lstrip(":").partition(".")[0]

                    # strip out all the html tags from the line
                    pline = re.sub(r"<[^>]*>", "", line.strip())
                    # print(timestamp+"|"+pline)
                    lines.append(timestamp + "|" + pline)
        return "\n".join(lines)

    def loadvideos(self):
        for entry in os.scandir(self.subsdir):
            if entry.name.endswith(".en.vtt"):
                # print("###############")
                # print(entry.name)
                m = re.match(r"^(.+?)-([a-zA-Z0-9\-_]{11})\.en(-GB)?\.vtt$", entry.name)
                title = m.group(1)
                stub = m.group(2)
                # print("title:\t", title)
                # print("stub:\t", stub)

                text = self.processvttfile(entry.path)

                descriptionfilename = title + "-" + stub + ".description"
                descriptionfilepath = os.path.join(self.subsdir, descriptionfilename)
                if os.path.exists(descriptionfilepath):
                    description = open(descriptionfilepath).read()
                else:
                    description = ""

                # print("text:\t", text[:100])
                # print("description:\t", description[:100])

                video = self.Video(title, stub, text, description)
                self.videos.append(video)

    def extractkeywords(self, query):
        boringwords = """
	a about all also am an and any as at back be because but by can come could do does did for from get go have he her him his how i if in is into it its just like make me my no not now of on one only or our out over say see she so some take than that the their them then there these they this time to up us use was we what when which who will with would your know find where something
	name remember video talk talked talking talks rob robert
	""".split()
        boringwords = [w.strip() for w in boringwords]

        keywords = query.lower().split()
        keywords = [w.strip("\"'?.,!") for w in keywords if w not in boringwords]
        # print("keywords are:", keywords)
        return keywords

    def sortbyrelevance(self, videos, searchstring, reverse=False):
        query = searchstring
        keywords = self.extractkeywords(searchstring)
        print('Video Keywords:, "%s"' % keywords)

        for video in videos:
            video.score = 0
            # print(video.title,type(video.text))
            for keyword in keywords:
                # print(keyword, video.score)
                video.score += (
                    3.0
                    * video.title.lower().count(keyword.lower())
                    / (len(video.title) + 1)
                )
                video.score += (
                    1.0
                    * video.description.lower().count(keyword.lower())
                    / (len(video.description) + 1)
                )
                video.score += (
                    1.0
                    * video.text.lower().count(keyword.lower())
                    / (len(video.text) + 1)
                )
                # print(video.score)

        return sorted(videos, key=(lambda v: v.score), reverse=reverse)

    def search(self, query):
        result = self.sortbyrelevance(self.videos, query, reverse=True)
        print("Search Result:", result)

        bestscore = result[0].score
        if bestscore == 0:
            return []

        matches = [result[0]]

        for r in result[1:10]:
            if r.score > 0:
                print(r)
            if r.score > (bestscore / 2.0):
                matches.append(r)

        return matches

    def canProcessMessage(self, message, client=None):
        if self.isatme(message):
            text = self.isatme(message)

            m = re.match(self.re_search, text)
            if m:
                return (9, "")

        # This is either not at me, or not something we can handle
        return (0, "")

    def conversationalise(self, result):
        video = result[0]
        videodesc = '"%s" %s' % (video.title, video.url)

        reply = "This video seems relevant:\n" + videodesc

        if len(result) > 1:
            reply += "\nIt could also be:\n"
            for video in result[1:5]:
                reply += '- "%s" <%s>\n' % (video.title, video.url)

        return reply

    async def processMessage(self, message, client):
        if self.isatme(message):
            text = self.self.isatme(message)

            m = re.match(self.re_search, text)
            if m:
                query = m.group("query")
                print('Video Query is:, "%s"' % query)
                result = self.search(query)
                if result:
                    print("Result:", result)
                    return (10, self.conversationalise(result))
                else:
                    return (8, "No matches found")
            else:
                print("Shouldn't be able to get here")
                return (0, "")

    def __str__(self):
        return "Video Search Manager"


if __name__ == "__main__":

    module = VideoSearch()

    while True:
        query = input()
        print(module.search(query))

    exit()

    takenextline = False
    timestamp = "00:00"
    prevline = ""

    # with open(sys.argv[1]) as vttfile:
    # 	for line in vttfile.readlines():

    # 		if takenextline:
    # 			if line != prevline:
    # 				print(timestamp + " " + line)
    # 			prevline = line
    # 			takenextline = False
    # 		else:
    # 			match = re.match(r"\d\d:\d\d:\d\d\.\d\d\d", line)
    # 			if match:
    # 				timestamp = match.group(0)
    # 				timestamp = timestamp.lstrip("0").lstrip(":").partition(".")[0]
    # 				# print(timestamp)
    # 				takenextline = True

    with open(sys.argv[1]) as vttfile:
        for line in vttfile.readlines():
            m = re.search(r"<[^>]*>", line)
            if m:
                timestamp = m.group(0)  # the timestamp for the start of the line

                # remove the brackets, leading zeros, and milliseconds
                # 00:10:17.630 becomes 10:17
                timestamp = timestamp.lstrip("0<>").lstrip(":").partition(".")[0]

                # strip out all the html tags from the line
                pline = re.sub(r"<[^>]*>", "", line.strip())
                print(timestamp + "|" + pline)
