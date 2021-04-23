from api.semanticwiki import SemanticWiki
from utilities import utils
from collections import Counter
import re


query_result = utils.wiki.post(
    {
        "action": "ask",
        "format": "json",
        "api_version": "2",
        "query": "[[Category:Questions]] |?Question|?CommentURL|?Asker|sort=AskDate|order=desc|limit=3000",
    }
)

# print(len(query_result["query"]["results"].keys()))
count = 0
all_pages = {}

for k, v in query_result["query"]["results"].items():
    #print(k)
    #print(v)
    
    utils.wiki.set_question_property(k, "titleoverride", k)
    
    commentUrl = v["printouts"]["CommentURL"]
    asker = v["printouts"]["Asker"]
    
    if not commentUrl or not asker:
        print(k, end = " doesnt have a propper url\n")
        continue
    
    video_url, commentId = commentUrl[0].split("&lc=")
    #print(video_url, end = " - ")
    #print(commentId)
    videoTitle = utils.get_title(video_url)[0]
    
    new_title = asker[0]["fulltext"] + "'s question on " videoTitle  " id=" + commentId
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
#print(Counter(all_pages.keys()).most_common(2))
#print(Counter(all_pages.values()).most_common(2))