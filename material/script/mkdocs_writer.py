import concurrent.futures
import glob
import json
import os
from typing import Any, List, Optional, TextIO

import requests
from config.colors import colors
from config.gsheet import sheet
from requests.adapters import Response
from requests.sessions import Session
from schema.metadata import Metadata, StatStatusPair
from schema.problem import Problem, TopicTag
from datetime import date


class MkdocsWriter:
  def __init__(self, argv: List[str]):
    self.records: List[dict[str, str]] = sheet.get_all_records()
    self.session: Session = requests.Session()
    # json_data = json.loads(self.session.get(
    #     "https://leetcode.com/api/problems/all",
    #     timeout=10,
    # ).content.decode("utf-8"))
    try:
        response = self.session.get("https://leetcode.com/api/problems/all", timeout=10)
        response.raise_for_status()  # Check if the request was successful
        content = response.content.decode("utf-8")
        if not content:
            raise ValueError("Received empty response from the API")
        json_data = json.loads(content)
    except requests.RequestException as e:
        raise RuntimeError(f"Error fetching data from LeetCode API: {e}")
    except json.JSONDecodeError as e:
        raise ValueError(f"Error decoding JSON response: {e}")
    self.user_data = Metadata.from_dict(json_data)
    self.stat_status_pairs = self.user_data.stat_status_pairs
    self.stat_status_pairs.sort(key=lambda x: x.stat.frontend_question_id)
    self.sols_path = "docs/solutions/"
    self.problems_path = "docs/LeetCode_Problems/"
    self.article_path = "docs/LeetCode_Articles/articles/"

    if len(argv) == 2 and argv[1] == '--mock':
      self.stat_status_pairs = self.stat_status_pairs[:2]
      self.records = self.records[:2]

    if not os.path.exists(self.problems_path):
      os.makedirs(self.problems_path)

  def write_mkdocs(self) -> None:
    with open("mkdocs.yml", "a+", encoding="utf-8") as f:
      f.write("  - LeetCode Solution:\n")
      f.write("    - preface.md\n")
      f.write("    - Problems:\n")
      f.write("      - Solution:\n")
      for stat_status_pair in self.stat_status_pairs:
        frontend_question_id: int = stat_status_pair.stat.frontend_question_id
        f.write(
            f'        - "{frontend_question_id}. {stat_status_pair.stat.question__title}": LeetCode_Problems/{str(frontend_question_id).zfill(4)}.md\n')
      f.write("  - About:\n")
      f.write("    - about/about.md\n")
      f.write("    - about/contributing.md\n")

  #-----------TESTING------------------------------

  def write_article(self) -> None:
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
      futures = [executor.submit(self._write_article, stat_status_pair)
                 for stat_status_pair in self.stat_status_pairs]
      concurrent.futures.wait(futures)

  def _write_article(self, stat_status_pair: StatStatusPair) -> None:
    frontend_question_id: int = stat_status_pair.stat.frontend_question_id
    filled_question_id = str(frontend_question_id).zfill(4)
    slug: str = stat_status_pair.stat.question__title_slug
    json_dict: dict = self._get_problem_by_slug(slug)
    problem = Problem.from_dict(json_dict)
    print(f"Write Articles {frontend_question_id}. {problem.title}...")

    with open(f"{self.article_path}{filled_question_id}.md", "w", encoding="utf-8") as f:
      f.write("---\n")
      f.write("authors: [AkashSingh3031]\n")
      f.write("categories:\n  - ")
      self._write_art(f, self._get_tags(problem.topicTags))
      f.write("comments: true\n")
      f.write("date:\n")
      f.write("  created: 2023-10-08\n")
      f.write(f"  updated: {date.today()}\n")
      f.write("tags:\n  - ")
      difficulty_string = f"{problem.difficulty}"
      self._write_art(f, difficulty_string)
      f.write("  - ")
      self._write_art(f, self._get_tags(problem.topicTags))
      f.write("title: ")
      f.write('"')
      f.write(self._get_title(frontend_question_id, problem.title))
      f.write('"')
      f.write("\n---\n\n")
      f.write("<!-- more -->\n\n")
      f.write("/// details | Problem\n")
      f.write("    open: True\n")
      f.write("    type: question\n\n")
      f.write(json_dict['content'])
      f.write("\n\n///\n")
      # matches = glob.glob(f"{self.sols_path}{filled_question_id}*")
      # if not matches:
      #   return
      # self._write_codes(
      #     f, self.records[frontend_question_id - 1], filled_question_id, matches[0])

  def _get_title(self, problem_no: int, title: str) -> str:
    display_title: str = f"{problem_no}. {title}"
    return display_title

  def _get_tags(self, topic_tags: List[TopicTag]) -> str:
    tag_strings: List[str] = []
    for topic_tag in topic_tags:
      tag_string: str = f"{topic_tag.name.replace('-', '--')}"
      tag_strings.append(tag_string)
    return '\n  - '.join(tag_strings)

  def _write_art(self, f: TextIO, s: str) -> None:
    f.write(s)
    f.write('\n')

  #-----------------------------------------------
  
  def write_problems(self) -> None:
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
      futures = [executor.submit(self._write_problem, stat_status_pair)
                 for stat_status_pair in self.stat_status_pairs]
      concurrent.futures.wait(futures)

  def _write_problem(self, stat_status_pair: StatStatusPair) -> None:
    frontend_question_id: int = stat_status_pair.stat.frontend_question_id
    filled_question_id = str(frontend_question_id).zfill(4)
    slug: str = stat_status_pair.stat.question__title_slug
    json_dict: dict = self._get_problem_by_slug(slug)
    problem = Problem.from_dict(json_dict)
    print(f"Write Problems {frontend_question_id}. {problem.title}...")

    with open(f"{self.problems_path}{filled_question_id}.md", "w", encoding="utf-8") as f:
      link = f'https://leetcode.com/problems/{slug}'
      emoji = self._get_emoji(problem.likes, problem.dislikes)
      self._write(f, self._get_display_title(
          frontend_question_id, problem.title, link, emoji))
      difficulty_color: str = self._get_difficulty_color(problem.difficulty)
      difficulty_string = f"![](https://img.shields.io/badge/-{problem.difficulty}-{difficulty_color}.svg?style=for-the-badge)"
      self._write(f, difficulty_string)
      self._write(f, self._get_tags_string(problem.topicTags))
      f.write("\n\n/// details | Problem\n")
      f.write("    open: True\n")
      f.write("    type: question\n\n")
      f.write(json_dict['content'])
      f.write("\n\n///\n")
      matches = glob.glob(f"{self.sols_path}{filled_question_id}*")
      if not matches:
        return
      self._write_codes(
          f, self.records[frontend_question_id - 1], filled_question_id, matches[0])

  def _write(self, f: TextIO, s: str) -> None:
    f.write(s)
    f.write('\n\n')

  def _write_codes(self, f: TextIO, gsheet_record: Any, filled_question_id: str,
                   path: str) -> None:
    time_complexities: List[str] = gsheet_record["Time"].split("; ")
    space_complexities: List[str] = gsheet_record["Space"].split("; ")
    ways: List[str] = gsheet_record["Ways"].split("; ")
    if len(ways) > 1:
      # For each way to solve this problem
      approach_index = 1
      for way, time_complexity, space_complexity in zip(
              ways, time_complexities, space_complexities):
        f.write(f"## Approach {approach_index}: {way}\n\n")
        f.write(f"- [x] **Time:** {time_complexity}\n")
        f.write(f"- [x] **Space:** {space_complexity}\n")
        f.write("\n")
        self._write_code(f, filled_question_id, path, approach_index)
        approach_index += 1
    else:
      if time_complexities:
        f.write(f"- [x] **Time:** {time_complexities[0]}\n")
      if space_complexities:
        f.write(f"- [x] **Space:** {space_complexities[0]}\n")
      f.write("\n")
      self._write_code(f, filled_question_id, path, 1)

  def _write_code(self, f: TextIO, filled_question_id: str, problem_path: str,
                  approach_index: int) -> None:
    for extension, lang, tab in [
        ("cpp", "cpp", "C++"),
        ("java", "java", "Java"),
        ("py", "python", "Python"),
    ]:
      suffix: str = "" if approach_index == 1 else f"-{approach_index}"
      code_file_dir = f"{problem_path}/{filled_question_id}{suffix}.{extension}"

      if not os.path.exists(code_file_dir):
        continue

      f.write(f'=== "{tab}"\n\n')
      with open(code_file_dir) as code_file:
        code = ["    " + line for line in code_file.readlines()]
        f.write(f"    ```{lang}\n")
        for line in code:
          f.write(line)
        f.write("\n")
        f.write("    ```")
        f.write("\n\n")

  def _get_problem_by_slug(self, slug: str) -> Problem:
    url = "https://leetcode.com/graphql"
    params = {
        "operationName": "questionData",
        "variables": {"titleSlug": slug},
        "query": """
            query questionData($titleSlug: String!) {
              question(titleSlug: $titleSlug) {
                title
                difficulty
                content
                likes
                dislikes
                topicTags {
                  name
                }
              }
            }
        """
    }

    json_data = json.dumps(params).encode("utf8")
    headers = {"Content-Type": "application/json",
               "Referer": f"https://leetcode.com/problems/{slug}"}
    
    res: Optional[Response] = None
    while not res:
      res = self.session.post(url, data=json_data, headers=headers, timeout=10)
    question: dict = res.json()
    return question["data"]["question"]

  def _get_display_title(self, problem_no: int, title: str, link: str, emoji: str) -> str:
    display_title: str = f"# [{problem_no}. {title}]({link})"
    if emoji:
      display_title += " " + emoji
    return display_title

  def _get_difficulty_color(self, difficulty: str) -> str:
    if difficulty == "Easy":
      return "00a690"
    if difficulty == "Medium":
      return "ffaf00"
    return "ff284b"

  def _get_tags_string(self, topic_tags: List[TopicTag]) -> str:
    tag_strings: List[str] = []
    for topic_tag in topic_tags:
      if topic_tag.name in colors:
        color: str = colors[topic_tag.name]
        tag_string: str = f"![](https://img.shields.io/badge/-{topic_tag.name.replace('-', '--')}-{color}.svg?style=plastic)"
        tag_strings.append(tag_string)
    return ' '.join(tag_strings)

  def _get_emoji(self, likes: int, dislikes: int) -> str:
    votes: int = likes + dislikes
    if votes == 0:
      return ""
    likes_percentage: float = likes / votes
    if likes_percentage > 0.8:
      return ":thumbsup:"
    if likes_percentage < 0.5:
      return ":thumbsdown:"
    return ""
