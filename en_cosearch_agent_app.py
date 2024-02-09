import time
import ast
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

from agents.cosearch_agent import CoSearchAgent
from agents.search_engine import SearchEngine
from memory.cosearch_agent_memory import Memory
from memory.rag_results_memory import SearchMemory
from memory.click_memory import ClickMemory
from utils import (
    get_conversation_history,
    replace_utterance_ids,
    get_user_info,
    get_channel_info,
    send_rag_answer,
    send_clarify_question,
    update_rag_answer,
    SERPAPI_KEY,
    OPENAI_KEY,
    SQL_PASSWORD,
)

# Slack API tokens
SLACK_BOT_TOKEN = "bot_token"
SLACK_APP_TOKEN = "app_token"
BOT_ID = "bot_id"

app = App(token=SLACK_BOT_TOKEN)

search_engine = SearchEngine(api_key=SERPAPI_KEY)
agent = CoSearchAgent(search_engine=search_engine, api_key=OPENAI_KEY)

memory = Memory(sql_password=SQL_PASSWORD)
search_memory = SearchMemory(sql_password=SQL_PASSWORD)
click_memory = ClickMemory(sql_password=SQL_PASSWORD)

channel_id2names = get_channel_info(table_name="channel_info")
user_id2names = get_user_info(table_name="user_info")
user_id2names["bot_id"] = "CoSearchAgent"


@app.action("click")
def click_link(ack, body):
    channel_name, user_name = body["channel"]["name"], body["user"]["username"]
    event_ts = body["container"]["message_ts"]

    search_info = search_memory.load_search_results_from_timestamp(table_name=f"{channel_name}_search",
                                                                   timestamp=str(event_ts))

    action = body["actions"][0]
    link, ts = action["value"], action["action_ts"]

    click_memory.create_table_if_not_exists(f"{channel_name}_click")
    click_memory.write_into_memory(table_name=f"{channel_name}_click",
                                   click_info={
                                       "user_name": user_name,
                                       "query": search_info["query"],
                                       "link": link,
                                       "timestamp": ts
                                   })

    ack()


@app.action("next")
def return_next_page(ack, body, client):
    channel_id, user_id = body['channel']['id'], body['user']['id']
    channel_name, user_name = channel_id2names[channel_id], user_id2names[user_id]
    event_ts = body["container"]["message_ts"]

    search_info = search_memory.load_search_results_from_timestamp(table_name=f"{channel_name}_search",
                                                                   timestamp=str(event_ts))
    search_results = ast.literal_eval(search_info["search_results"])

    start, end = search_info["start"], search_info["end"]
    if start + 2 < len(search_results):
        start = start + 2
        end = end + 2

    ts = update_rag_answer(client=client, query=search_info["query"], channel_id=channel_id, user_id=user_id,
                           answer=search_info["answer"], references=search_results, start=start, end=end,
                           ts=event_ts)["ts"]

    search_memory.write_into_memory(table_name=f"{channel_name}_search", search_info={
        "user_name": user_name,
        "query": search_info["query"],
        "answer": search_info["answer"],
        "search_results": str(search_results),
        "start": start,
        "end": end,
        "click_time": time.time(),
        "timestamp": ts
    })

    ack()


@app.action("previous")
def return_previous_page(ack, body, client):
    channel_id, user_id = body['channel']['id'], body['user']['id']
    channel_name, user_name = channel_id2names[channel_id], user_id2names[user_id]
    event_ts = body["container"]["message_ts"]

    search_info = search_memory.load_search_results_from_timestamp(table_name=f"{channel_name}_search",
                                                                   timestamp=str(event_ts))
    search_results = ast.literal_eval(search_info["search_results"])

    start, end = search_info["start"], search_info["end"]
    if start - 2 >= 0:
        start = start - 2
        end = end - 2

    ts = update_rag_answer(client=client, query=search_info["query"], channel_id=channel_id, user_id=user_id,
                           answer=search_info["answer"], references=search_results, start=start, end=end,
                           ts=event_ts)["ts"]

    search_memory.write_into_memory(table_name=f"{channel_name}_search", search_info={
        "user_name": user_name,
        "query": search_info["query"],
        "answer": search_info["answer"],
        "search_results": str(search_results),
        "start": start,
        "end": end,
        "click_time": time.time(),
        "timestamp": ts
    })

    ack()


@app.event("message")
def handle_message_event(ack, event, client):
    channel_id, user_id, ts = event["channel"], event["user"], event["ts"]
    channel_name, user_name = channel_id2names[channel_id], user_id2names[user_id]
    if user_id == BOT_ID:
        return

    user_utterance = replace_utterance_ids(event["text"].strip("\n").strip(), id2names=user_id2names)

    memory.create_table_if_not_exists(table_name=channel_name)
    memory.write_into_memory(
        table_name=channel_name,
        utterance_info={"speaker": user_name, "utterance": user_utterance, "convs": "",
                        "query": "", "rewrite_query": "", "rewrite_thought": "",
                        "clarify": "", "clarify_thought": "", "clarify_cnt": 0, "search_results": "",
                        "infer_time": "", "reply_timestamp": "", "reply_user": "", "timestamp": ts}
    )

    pattern = "@CoSearchAgent"
    if user_utterance.startswith(pattern):
        convs = get_conversation_history(client=client, channel_id=channel_id, bot_id=BOT_ID,
                                         user_id2names=user_id2names, ts=ts)
        query = user_utterance.lstrip(pattern).strip()

        rewrite_query, rewrite_time = agent.rewrite_query(user=user_name, query=query, convs=convs)
        clarify_cnt = memory.get_clarify_cnt_for_speaker(table_name=channel_name, reply_user=user_name)

        if clarify_cnt > 0:
            clarify_thought, clarify_question = "", ""
            clarify_time = 0
        else:
            clarify_output, clarify_time = agent.ask_clarify_query(user=user_name, query=rewrite_query, convs=convs)
            clarify_output = clarify_output.split("\n")
            clarify_thought = clarify_output[0].lstrip("Judgment thought: ").strip()
            clarify_question = clarify_output[1].lstrip("Clarifying question: ").strip()
            if "None" not in clarify_question:
                response_ts = send_clarify_question(client=client, channel_id=channel_id, user_id=user_id,
                                                    clarify_question=clarify_question)["ts"]

                memory.write_into_memory(
                    table_name=channel_name,
                    utterance_info={"speaker": "CoSearchAgent", "utterance": clarify_question, "convs": convs,
                                    "query": query, "rewrite_query": rewrite_query, "rewrite_thought": "",
                                    "clarify": clarify_question, "clarify_thought": clarify_thought,
                                    "clarify_cnt": clarify_cnt+1, "search_results": "",
                                    "infer_time": str({"rewrite": rewrite_time, "clarify": clarify_time}),
                                    "reply_user": user_name, "reply_timestamp": ts, "timestamp": response_ts}
                )
                return

        answer, search_results, extract_time, answer_time = agent.generate_answer(rewrite_query)
        response_ts = send_rag_answer(client=client, channel_id=channel_id, query=rewrite_query, user_id=user_id,
                                      answer=answer, references=search_results)["ts"]

        memory.write_into_memory(
            table_name=channel_name,
            utterance_info={"speaker": "CoSearchAgent", "utterance": answer, "convs": convs,
                            "query": query, "rewrite_query": rewrite_query, "rewrite_thought": "",
                            "clarify": clarify_question, "clarify_thought": clarify_thought, "clarify_cnt": 0,
                            "search_results": str(search_results),
                            "infer_time": str({"rewrite": rewrite_time, "clarify": clarify_time,
                                               "extract": extract_time, "answer": answer_time}),
                            "reply_timestamp": ts, "reply_user": user_name, "timestamp": response_ts}
        )

        search_memory.create_table_if_not_exists(table_name=f"{channel_name}_search")
        search_memory.write_into_memory(
            table_name=f"{channel_name}_search",
            search_info={"user_name": user_name, "query": rewrite_query, "answer": answer,
                         "search_results": str(search_results), "start": 0, "end": 2,
                         "click_time": time.time(), "timestamp": response_ts}
        )

    ack()


if __name__ == "__main__":
    SocketModeHandler(app, SLACK_APP_TOKEN).start()
