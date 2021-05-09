from api.semanticwiki import SemanticWiki
from utilities import utils
from collections import Counter
import re


answer_query_result = utils.wiki.post(
    {
        "action": "ask",
        "format": "json",
        "api_version": "2",
        "query": "[[Category:Answers]]|?AnswerTo|limit=3000",
    }
)

print("ANSWERS:")
for k, v in answer_query_result["query"]["results"].items():
    print(k)
    # print(v)
    if not v["printouts"]["AnswerTo"] or not "fulltext" in v["printouts"]["AnswerTo"][0]:
        print("page answerto was already broken")
        continue

    new_question_title = v["printouts"]["AnswerTo"][0]["fulltext"].replace("=", ":")

    if new_question_title == v["printouts"]["AnswerTo"][0]["fulltext"]:
        print(k, end=" was already changed\n")
        continue

    # print(new_question_title)
    # print(v.keys())
    utils.wiki.post(
        {
            "action": "pfautoedit",
            "form": "Answer",
            "target": k,
            "format": "json",
            "query": "Answer[{0}]={1}".format("answerto", new_question_title),
        }
    )


print("QUESTIONS:")
query_result = utils.wiki.post(
    {
        "action": "ask",
        "format": "json",
        "api_version": "2",
        "query": "[[Category:Questions]]|?CommentURL|sort=AskDate|order=desc|limit=4000",  # |[[CommentURL::https://www.youtube.com/watch?v=Ao4jwLwT36M&lc=UgzxCF-1ur3SJ7eiO1R4AaABAg]]
    }
)

count = 0
all_pages = {}
i = 0
l = len(query_result["query"]["results"].keys())


for k, v in query_result["query"]["results"].items():
    print(k)
    # print(v)
    i += 1
    if i % 25 == 0:
        print("PROGRESS: [" + str(i) + "/" + str(l) + "]")

    new_title = k.replace("=", ":")

    if new_title.replace("_", " ") in query_result["query"]["results"]:
        print(k, end=" was already moved\n")
        continue

    print(
        utils.wiki.post(
            {
                "action": "move",
                "from": k,
                "to": new_title,
                "format": "json",
                "noredirect": "1",
                "token": utils.wiki._token,
            }
        )
    )


"""
query_result = utils.wiki.post(
        {
        "action": "ask",
        "format": "json",
        "api_version": "2",
        "query": "[[Category:Questions]]|[[CommentURL::https://www.youtube.com/watch?v=Ao4jwLwT36M&lc=UgzxCF-1ur3SJ7eiO1R4AaABAg]]|?Question|?CommentURL|?Asker|sort=AskDate|order=desc|limit=10",#
    }
)

# print(len(query_result["query"]["results"].keys()))
count = 0
all_pages = {}
i = 0
l = len(query_result["query"]["results"].keys())


for k, v in query_result["query"]["results"].items():
    print(k)
    #print(v)
    i+=1
    if i % 25 == 0: print("PROGRESS: [" + str(i) + "/" + str(l) + "]")
    
    
    commentUrl = v["printouts"]["CommentURL"]
    asker = v["printouts"]["Asker"]
    
    
    if not commentUrl or not asker:
        print(k, end = " doesnt have a propper url\n")
        continue
    
    video_url, commentId = commentUrl[0].split("&lc=")
    #print(video_url, end = " - ")
    #print(commentId)
    titles = utils.get_title(video_url)
    if(titles):
        videoTitle = utils.get_title(video_url)[0]
    else:
        videoTitle = "Video Title Unknown"
    
    display_tile = asker[0]["fulltext"] + "'s question on " + videoTitle
    
    new_title =  display_tile + " id=" + commentId

    if(new_title.replace("_", " ") in query_result["query"]["results"]):
        print(k, end = " was already moved\n")
        continue
    
    utils.wiki.set_question_property(k, "titleoverride", display_tile)
    
    
    print(k + " -> " + new_title)
    
    print(utils.wiki.post(
        {
            "action":"move",
            "from":k,
            "to": new_title,
            "format":"json",
            "token": utils.wiki._token
        }
    ))
    
    all_pages[k] = new_title
    
    ##check for duplicates
    #question = v["printouts"]["Question"]
    #if question:
    #    if not question[0] in all_pages:
    #        all_pages[question[0]] = []
    #    all_pages[question[0]].append(k)
    
    ## Deal with wrong timestamps
    #match = re.match(r".*\d\dT\d\d:\d\d:\d\d\.\d\d", k)
    #if match:
    #    print(k)


for k, v in all_pages.items():
    if len(v)>1:
        print(v, end=":  ")
        if(len(k)>100):
            print(k[:100])
        else:
            print(k)
 

print("Finished")
print(all_pages)
#print(Counter(all_pages.keys()).most_common(2))
#print(Counter(all_pages.values()).most_common(2))
# """
