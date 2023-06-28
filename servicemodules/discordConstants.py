# NOTE(ProducerMatt): mostly deprecated as Stampy codebase may be used on
# multiple servers, see ../config.py. Should eventually be removed entirely with
# blessing of dev team.

from config import ENVIRONMENT_TYPE

# fmt:off

################################
# RAW DATA FOR ALL CHANNEL IDS #
################################

welcome_channel_id: str = {"production": "743842679741481051", "development": "817518666349412352"}[ENVIRONMENT_TYPE]
introductions_channel_id: str = {"production": "741764243753402389", "development": "817518698339500053"}[ENVIRONMENT_TYPE]

core_category_id: str = {"production": "1036026077576962198", "development": "-2"}[ENVIRONMENT_TYPE]
general_channel_id: str = {"production": "677546901339504646", "development": "783123903382814723"}[ENVIRONMENT_TYPE]
ai_safety_questions_channel_id: str = {"production": "1036026287459934298", "development": "-2"}[ENVIRONMENT_TYPE]
aligned_intelligences_only_channel_id: str = {"production": "948354810002944070", "development": "-2"}[ENVIRONMENT_TYPE]
voice_channel_id: str = {"production": "677546901339504648", "development": "783123903382814724"}[ENVIRONMENT_TYPE]
stampy_category_id: str = {"production": "812043478321987635", "development": "-2"}[ENVIRONMENT_TYPE]
stampy_dev_channel_id: str = {"production": "758062805810282526", "development": "817518145472299009"}[ENVIRONMENT_TYPE]

wiki_channel_id: str = {"production": "835222827207753748", "development": "871715944114819092"}[ENVIRONMENT_TYPE]
talk_to_stampy_channel_id: str = {"production": "808138366330994688", "development": "817518440192409621"}[ENVIRONMENT_TYPE]
wiki_feed_channel_id: str = {"production": "819348467876364288", "development": "818635466478846033"}[ENVIRONMENT_TYPE]
stampy_dev_priv_channel_id: str = {"production": "736247813616304159", "development": "817518389848309760"}[ENVIRONMENT_TYPE]
stampy_error_log_channel_id: str = {"production": "1017527224540344380", "development": "1017531179664150608"}[ENVIRONMENT_TYPE]
off_topic_channel_id: str = {"production": "997857170647433257", "development": "-2"}[ENVIRONMENT_TYPE]
memes_channel_id: str = {"production": "843628797270294568", "development": "-2"}[ENVIRONMENT_TYPE]

other_channels_category_id: str = {"production": "677546901339504642", "development": "783123903382814721"}[ENVIRONMENT_TYPE]
ai_channel_id: str = {"production": "817511894671294524", "development": "817517982832918558"}[ENVIRONMENT_TYPE]
not_ai_channel_id: str = {"production": "757908690165694546", "development": "817518001237655552"}[ENVIRONMENT_TYPE]
events_channel_id: str = {"production": "789918737415012384", "development": "817518818951430184"}[ENVIRONMENT_TYPE]
projects_channel_id: str = {"production": "787117276960522280", "development": "817518806472589342"}[ENVIRONMENT_TYPE]
book_club_channel_id: str = {"production": "929823603766222919", "development": "-2"}[ENVIRONMENT_TYPE]
dialogues_with_stampy_channel_id: str = {"production": "1013976966564675644", "development": "-2"}[ENVIRONMENT_TYPE]
meta_channel_id: str = {"production": "741332060031156296", "development": "817518780509847562"}[ENVIRONMENT_TYPE]
meta_editing_channel_id: str = {"production": "1088468403406258196", "development": "1123312639016181810"}[ENVIRONMENT_TYPE]

archive_category_id: str = {"production": "929823542818766948", "development": "-2"}[ENVIRONMENT_TYPE]
voice_context_channel_id: str = {"production": "810261871029387275", "development": "-2"}[ENVIRONMENT_TYPE]
editing_channel_id: str = {"production": "835222827207753748", "development": "1081612961275187250"}[ENVIRONMENT_TYPE]

test_channel_id: str = {"production": "-99", "development": "803448149946662923"}[ENVIRONMENT_TYPE]
bot_owner_dms_id: str = {"production": "-1", "development": "736241264856662038"}[ENVIRONMENT_TYPE] #TODO: replace "-1" with the id for robs DM with stampy,

# TODO: it would be good if we had a test that warned us if the above did not actually match up with the server layout

########################
# ID DERIVED VARIABLES #
########################

automatic_question_channel_id = general_channel_id  # TODO: should this be ai_safety_questions_channel_id?

stampy_control_channel_ids: tuple[str, ...] = (test_channel_id, stampy_dev_priv_channel_id, stampy_dev_channel_id, talk_to_stampy_channel_id, bot_owner_dms_id)


####################################################
# USER/ROLE IDs (not complete due to lack of need) #
####################################################

bot_admin_role_id: str = {"production": "819898114823159819", "development": "948709263461711923"}[ENVIRONMENT_TYPE]
bot_dev_role_id: str = {"production": "736247946676535438", "development": "817518998148087858"}[ENVIRONMENT_TYPE]
member_role_id: str = {"production": "945033781818040391", "development": "947463614841901117"}[ENVIRONMENT_TYPE]
# pretty sure can-invite is deprecated, but putting it here for completeness

rob_id: str = "181142785259208704"
stampy_id: str = "736241264856662038"
