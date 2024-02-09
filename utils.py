import pymysql
import nltk
import re
from rouge import Rouge

# API keys
SERPAPI_KEY = "f8f90686f6e5e62111b1beb91ea45586ae0fff55ea9a1076f5ee5111edbb2162"
OPENAI_KEY = "sk-rhaQindC3DHqfAru86Eb61A7B44f465dA97d13D794465248"
OPENAI_URL = "https://oneapi.xty.app/v1"

# Database password
SQL_PASSWORD = "1675081855"


def get_table_info(table_name):
    connection = pymysql.connect(host='localhost', user='root', passwd=SQL_PASSWORD, port=3306, db="mysql")

    query = f"SELECT * FROM {table_name}"

    with connection.cursor() as cursor:
        cursor.execute(query)
        table_contents = cursor.fetchall()

    return table_contents


def get_channel_info(table_name="channel_info"):
    contents = get_table_info(table_name=table_name)
    channel_id2names = {content[1]: content[2] for content in contents}
    return channel_id2names


def get_user_info(table_name="user_info"):
    contents = get_table_info(table_name=table_name)
    user_id2names = {content[1]: content[2] for content in contents}
    return user_id2names


def send_rag_answer(client, channel_id, user_id, query, answer, references, start=0, end=2):
    formatted_answer = format_response(response=answer, user_id=user_id)
    response = client.chat_postMessage(
        channel=channel_id,
        blocks=send_answer_block(query, formatted_answer, references, start, end)
    )
    return response


def send_utterance(client, channel_id, utterance):
    response = client.chat_postMessage(
        channel=channel_id,
        blocks=[
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": utterance
                }
            }
        ]
    )
    return response


def delete_utterance(client, channel_id, ts):
    client.chat_delete(
        channel=channel_id,
        ts=ts
    )


def update_rag_answer(client, channel_id, user_id, query, answer, references, ts, start=0, end=2):
    formatted_answer = format_response(response=answer, user_id=user_id)
    response = client.chat_update(
        channel=channel_id,
        ts=ts,
        blocks=send_answer_block(query, formatted_answer, references, start, end)
    )
    return response


def send_clarify_question(client, channel_id, user_id, clarify_question):
    clarify_question = format_response(response=clarify_question, user_id=user_id)
    response = client.chat_postMessage(
        channel=channel_id,
        blocks=[
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": clarify_question
                }
            }
        ]
    )
    return response


def send_answer(client, channel_id, user_id, answer):
    answer = format_response(response=answer, user_id=user_id)
    response = client.chat_postMessage(
        channel=channel_id,
        blocks=[
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": answer
                }
            }
        ]
    )
    return response


def get_conversation_history(client, channel_id, bot_id, user_id2names, ts, limit=20):
    messages = client.conversations_history(channel=channel_id, latest=ts, limit=limit)["messages"]
    convs = []
    for message in reversed(messages):
        if "已加入此频道" in message["text"]:
            continue
        if message["user"] == bot_id:
            convs.append(
                f"{user_id2names[message['user']]}: {replace_utterance_ids(message['blocks'][0]['text']['text'], user_id2names)}")
        else:
            convs.append(f"{user_id2names[message['user']]}: {replace_utterance_ids(message['text'], user_id2names)}")
    return "\n".join(convs)


def add_brackets_to_numbers(answer, threshold):
    def process_match(match):
        number = int(match.group(1))
        if number > threshold:
            return ''
        return f'[{match.group(1)}]'

    answer = re.sub(r'\[(\d+)\]', process_match, answer)
    answer = re.sub(r'(\[\d+\]\s*)+', lambda m: f' *{m.group()}* ', answer)
    return answer


def send_answer_block(query, answer, results, start, end):
    blocks = [{
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": add_brackets_to_numbers(answer, len(results))
        }
    }, {
        "type": "divider"
    }, {
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": f":mag: *{query}* ({len(results)} results)"
        }
    },
        {
            "type": "divider"
        }]
    for i, result in enumerate(results[start:end]):
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*[{start + i + 1}] {result['title']}*\n{result['snippet']}"
            },
            "accessory": {
                "type": "button",
                "text": {
                    "type": "plain_text",
                    "text": "Click",
                    "emoji": True
                },
                "value": result["link"],
                "url": result["link"],
                "action_id": f"click"
            }
        })
    blocks.append({
        "type": "divider"
    })
    blocks.append({
        "type": "actions",
        "elements": [
            {
                "type": "button",
                "text": {
                    "type": "plain_text",
                    "emoji": True,
                    "text": "Previous"
                },
                "style": "primary",
                "value": "click_me_123",
                "action_id": "previous"
            },
            {
                "type": "button",
                "text": {
                    "type": "plain_text",
                    "emoji": True,
                    "text": "Next"
                },
                "style": "primary",
                "value": "click_me_123",
                "action_id": "next"
            },
        ]
    })
    return blocks


def replace_utterance_ids(utterance, id2names):
    for user_id, user_name in id2names.items():
        id_pattern = f"<@{user_id}>"
        if id_pattern in utterance:
            utterance = utterance.replace(id_pattern, f"@{user_name}")
    return utterance


def format_response(response, user_id):
    return f"<@{user_id}> {response}"


def get_search_blocks(query, results, user_id, start, end):
    search_blocks = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"<@{user_id}> :mag: *{query}* ({len(results)} results)"
            }
        },
        {
            "type": "divider"
        }
    ]
    for i, result in enumerate(results[start:end]):
        search_blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*[{start + i + 1}] {result['title']}*\n{result['snippet']}"
            },
            "accessory": {
                "type": "button",
                "text": {
                    "type": "plain_text",
                    "text": "Click",
                    "emoji": True
                },
                "value": result["link"],
                "url": result["link"],
                "action_id": f"click"
            }
        })
    search_blocks.append({
        "type": "divider"
    })
    search_blocks.append({
        "type": "actions",
        "elements": [
            {
                "type": "button",
                "text": {
                    "type": "plain_text",
                    "emoji": True,
                    "text": "Previous"
                },
                "style": "primary",
                "value": "click_me_123",
                "action_id": "previous"
            },
            {
                "type": "button",
                "text": {
                    "type": "plain_text",
                    "emoji": True,
                    "text": "Next"
                },
                "style": "primary",
                "value": "click_me_123",
                "action_id": "next"
            },
        ]
    })

    return search_blocks


def send_search_results(client, query, search_results, channel_id, user_id, start=0, end=3):
    response = client.chat_postMessage(
        channel=channel_id,
        blocks=get_search_blocks(query=query,
                                 results=search_results,
                                 user_id=user_id,
                                 start=start,
                                 end=end)
    )
    return response


def update_search_results(client, query, search_results, channel_id, user_id, start, end, ts):
    response = client.chat_update(
        channel=channel_id,
        ts=ts,
        blocks=get_search_blocks(query=query,
                                 results=search_results,
                                 user_id=user_id,
                                 start=start,
                                 end=end)
    )
    return response


def chinese_sentence_tokenizer(text):
    pattern = r'[^？。！]*[？。！]'

    sentences = nltk.regexp_tokenize(text, pattern)
    sentences = [s.strip() for s in sentences if s.strip()]

    return sentences


def rouge1_similarity(reference, candidate):
    rouge = Rouge()
    scores = rouge.get_scores(candidate, reference)
    rouge_1_score = scores[0]['rouge-1']['f']
    return rouge_1_score


def get_top10_similar_results(answer, search_results):
    similarity_scores = [(index, rouge1_similarity(" ".join(answer), " ".join(result["snippet"])))
                         for index, result in enumerate(search_results) if result["snippet"]]
    similarity_scores.sort(key=lambda x: x[1], reverse=True)

    top5_results = [search_results[index] for index, _ in similarity_scores[:10]]
    return top5_results


def merge_citation_marks(answer, search_results, check_search_results):
    search_results = [item for sublist in [search_results, check_search_results] for item in sublist]
    search_results = list({tuple(sorted(d.items())): d for d in search_results}.values())
    search_results = get_top10_similar_results(answer, search_results)

    answer_segs = chinese_sentence_tokenizer(answer)
    for answer_seg in answer_segs:
        scores = {i: rouge1_similarity(answer_seg, result["snippet"]) for i, result in enumerate(search_results)}
        scores = sorted(scores.items(), key=lambda item: item[1], reverse=True)[:2]

        marks = [item[0] for item in scores if item[1] >= 0.3]
        if not marks:
            continue

        for mark in marks:
            answer_seg += f" *<{search_results[mark]['link']}|[{mark + 1}]>*"
    # for item, result in enumerate(search_results):
    #     scores = {i: rouge1_similarity(answer_seg, result["snippet"]) for i, answer_seg in enumerate(answer_segs)}
    #     scores = dict(sorted(scores.items(), key=lambda item: item[1], reverse=True))
    #     print(scores)
    #     marks = {k: v for k, v in scores.items() if v > 0.6}
    #     if not marks:
    #         max_key, max_value = max(scores.items(), key=lambda item: item[1])
    #         marks = {max_key: max_value}
    #
    #     for k in marks.keys():
    #         answer_segs[k] += f" *<{result['link']}|[{item + 1}]>*"
    #
    # answer = " ".join(answer_segs)
    # print(answer)
    return answer, search_results
