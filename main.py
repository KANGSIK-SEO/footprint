#!/usr/bin/env python3
"""
Footprint (Mini Git) - DAG 기반 커밋 이력(Provenance) 추적 및 버전 관리 CLI 시스템

이 모듈은 Git의 핵심 자료구조(DAG, 해시맵, 역색인)와 알고리즘(위상 정렬, BFS 최단 경로,
조상 탐색, 직접 구현한 정렬 알고리즘, LCS 기반 Diff)을 순수 Python으로 구현합니다.

제약 사항 준수:
- 그래프 전용 외부 라이브러리 미사용
- Python 표준 정렬 API 일체 미사용
"""

from __future__ import annotations

import hashlib
import random
import shlex
import sys
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Set, Tuple


# =====================================================================
# 1. 직접 구현한 정렬 알고리즘 모듈 (Custom Sorting Algorithms)
# =====================================================================

class Sorter:
    """
    Python 내장 정렬 API를 사용하지 않고 직접 구현한 정렬 알고리즘 클래스.
    - merge_sort: 안정 정렬(Stable Sort), 평균/최악 O(N log N)
    - quick_sort: 불안정 정렬(Unstable Sort), 평균 O(N log N), 최악 O(N^2)
    - insertion_sort: 안정 정렬(Stable Sort), 평균/최악 O(N^2)
    """

    @staticmethod
    def merge_sort(
        items: List[Any],
        key: Optional[Callable[[Any], Any]] = None,
        reverse: bool = False,
    ) -> List[Any]:
        """
        병합 정렬(Merge Sort)을 수행하여 새 리스트를 반환합니다.
        동일한 키 값을 가진 원소들의 기존 상대 순서가 유지되는 안정 정렬(Stable Sort)입니다.

        시간복잡도: 최선/평균/최악 모두 O(N log N)
        공간복잡도: O(N)
        """
        n = len(items)
        if n <= 1:
            return list(items)

        mid = n // 2
        left = Sorter.merge_sort(items[:mid], key=key, reverse=reverse)
        right = Sorter.merge_sort(items[mid:], key=key, reverse=reverse)
        return Sorter._merge(left, right, key=key, reverse=reverse)

    @staticmethod
    def _merge(
        left: List[Any],
        right: List[Any],
        key: Optional[Callable[[Any], Any]],
        reverse: bool,
    ) -> List[Any]:
        result: List[Any] = []
        i = 0
        j = 0
        len_l = len(left)
        len_r = len(right)

        while i < len_l and j < len_r:
            val_l = key(left[i]) if key else left[i]
            val_r = key(right[j]) if key else right[j]

            if not reverse:
                # 안정 정렬 보장: 왼쪽 원소가 작거나 같을 때 먼저 선택
                take_left = val_l <= val_r
            else:
                take_left = val_l >= val_r

            if take_left:
                result.append(left[i])
                i += 1
            else:
                result.append(right[j])
                j += 1

        while i < len_l:
            result.append(left[i])
            i += 1
        while j < len_r:
            result.append(right[j])
            j += 1

        return result

    @staticmethod
    def quick_sort(
        items: List[Any],
        key: Optional[Callable[[Any], Any]] = None,
        reverse: bool = False,
    ) -> List[Any]:
        """
        퀵 정렬(Quick Sort, 3-way 분할 방식)을 수행하여 새 리스트를 반환합니다.
        피벗을 중앙 인덱스 원소로 선택하여 이미 정렬된 입력에서의 최악 케이스를 완화합니다.

        시간복잡도: 평균 O(N log N), 최악 O(N^2)
        안정 정렬 여부: 불안정 정렬(Unstable Sort)
        """
        n = len(items)
        if n <= 1:
            return list(items)

        pivot_item = items[n // 2]
        pivot_val = key(pivot_item) if key else pivot_item

        less: List[Any] = []
        equal: List[Any] = []
        greater: List[Any] = []

        for item in items:
            val = key(item) if key else item
            if val < pivot_val:
                less.append(item)
            elif val > pivot_val:
                greater.append(item)
            else:
                equal.append(item)

        if not reverse:
            return (
                Sorter.quick_sort(less, key=key, reverse=reverse)
                + equal
                + Sorter.quick_sort(greater, key=key, reverse=reverse)
            )
        else:
            return (
                Sorter.quick_sort(greater, key=key, reverse=reverse)
                + equal
                + Sorter.quick_sort(less, key=key, reverse=reverse)
            )

    @staticmethod
    def insertion_sort(
        items: List[Any],
        key: Optional[Callable[[Any], Any]] = None,
        reverse: bool = False,
    ) -> List[Any]:
        """
        삽입 정렬(Insertion Sort)을 수행하여 새 리스트를 반환합니다.

        시간복잡도: 최선 O(N), 평균/최악 O(N^2)
        안정 정렬 여부: 안정 정렬(Stable Sort)
        """
        arr = list(items)
        for i in range(1, len(arr)):
            current_item = arr[i]
            current_val = key(current_item) if key else current_item
            j = i - 1

            while j >= 0:
                compare_val = key(arr[j]) if key else arr[j]
                should_shift = (compare_val > current_val) if not reverse else (compare_val < current_val)
                if should_shift:
                    arr[j + 1] = arr[j]
                    j -= 1
                else:
                    break
            arr[j + 1] = current_item
        return arr

    @staticmethod
    def benchmark(sizes: Optional[List[int]] = None) -> str:
        """
        보너스 과제: 서로 다른 정렬 알고리즘(Merge Sort, Quick Sort, Insertion Sort)의
        입력 크기에 따른 실행 시간을 비교합니다.
        """
        if sizes is None:
            sizes = [100, 500, 1000, 2500]

        lines: List[str] = []
        lines.append("=== Sorting Algorithm Benchmark (Random Integer Keys) ===")
        lines.append(f"{'Size (N)':>10} | {'Merge Sort (ms)':>16} | {'Quick Sort (ms)':>16} | {'Insertion Sort (ms)':>20}")
        lines.append("-" * 72)

        rng = random.Random(42)
        for n in sizes:
            sample = [rng.randint(1, 100000) for _ in range(n)]

            t0 = time.perf_counter()
            res_merge = Sorter.merge_sort(sample)
            t_merge = (time.perf_counter() - t0) * 1000.0

            t0 = time.perf_counter()
            res_quick = Sorter.quick_sort(sample)
            t_quick = (time.perf_counter() - t0) * 1000.0

            t0 = time.perf_counter()
            res_insert = Sorter.insertion_sort(sample)
            t_insert = (time.perf_counter() - t0) * 1000.0

            # 정합성 검증
            assert res_merge == res_quick == res_insert, "Sorting mismatch!"

            lines.append(
                f"{n:>10} | {t_merge:>13.3f} ms | {t_quick:>13.3f} ms | {t_insert:>17.3f} ms"
            )

        return "\n".join(lines)


# =====================================================================
# 2. 커밋 노드 및 커밋 그래프 (Commit Node & DAG)
# =====================================================================

@dataclass
class Commit:
    """
    Git의 단일 커밋 메타데이터를 표현하는 노드 클래스.
    필수 필드: hash, message, author, timestamp, parents
    """
    hash: str
    message: str
    author: str
    timestamp: str
    parents: List[str] = field(default_factory=list)
    seq: int = 0  # 생성 순서 추적용 시퀀스 번호


class CommitGraph:
    """
    방향성 비순환 그래프(DAG) 기반의 커밋 저장소 및 탐색 알고리즘 클래스.
    - commits: 해시맵(dict) 기반으로 커밋 해시를 통해 O(1) 조회
    - children_map: 부모 -> 자식 방향 인접 리스트 (위상 정렬 및 무방향 최단 경로 탐색용)
    """

    def __init__(self) -> None:
        self.commits: Dict[str, Commit] = {}
        self.children_map: Dict[str, List[str]] = {}
        self._seq_counter: int = 0

    def clear(self) -> None:
        """그래프 상태를 초기화합니다."""
        self.commits.clear()
        self.children_map.clear()
        self._seq_counter = 0

    def generate_unique_hash(self, author: str, message: str, timestamp: str) -> str:
        """
        세션 내 유일성이 보장되는 6자리 16진수 커밋 해시를 생성합니다.
        SHA-1 해시 앞 6자리를 사용하며, 충돌 시 시퀀스 솔트를 추가해 중복을 방지합니다.
        """
        salt = 0
        while True:
            raw = f"{self._seq_counter}:{author}:{timestamp}:{message}:{salt}"
            candidate = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:6]
            if candidate not in self.commits:
                return candidate
            salt += 1

    def add_commit(
        self,
        message: str,
        author: str,
        parents: List[str],
        timestamp: Optional[str] = None,
        custom_hash: Optional[str] = None,
    ) -> Commit:
        """
        새 커밋 노드를 생성하여 DAG에 추가합니다.
        새 커밋은 기존에 존재하는 커밋들만 부모로 지정할 수 있으므로 사이클이 생길 수 없으며
        항상 DAG(방향성 비순환 그래프) 불변성을 유지합니다.
        """
        for p_hash in parents:
            if p_hash not in self.commits:
                raise ValueError(f"Unknown commit: {p_hash}")

        self._seq_counter += 1
        if timestamp is None:
            # 연속 커밋 시에도 시간 순서가 명확히 구분되도록 시퀀스 오프셋 반영 가능
            base_time = datetime.now()
            timestamp = base_time.strftime("%Y-%m-%d %H:%M:%S")

        commit_hash = custom_hash if (custom_hash and custom_hash not in self.commits) else (
            self.generate_unique_hash(author, message, timestamp)
        )

        # 중복 부모 제거 (순서 유지)
        unique_parents: List[str] = []
        for p in parents:
            if p not in unique_parents:
                unique_parents.append(p)

        commit = Commit(
            hash=commit_hash,
            message=message,
            author=author,
            timestamp=timestamp,
            parents=unique_parents,
            seq=self._seq_counter,
        )

        self.commits[commit_hash] = commit
        if commit_hash not in self.children_map:
            self.children_map[commit_hash] = []

        for p_hash in unique_parents:
            if p_hash not in self.children_map:
                self.children_map[p_hash] = []
            self.children_map[p_hash].append(commit_hash)

        return commit

    def get_commit(self, commit_hash: str) -> Optional[Commit]:
        """해시맵을 통해 O(1) 시간복잡도로 커밋을 조회합니다."""
        return self.commits.get(commit_hash)

    def topological_sort(self) -> List[Commit]:
        """
        Kahn 알고리즘(진입차수 기반 위상 정렬)을 사용하여
        '부모 커밋이 항상 자식 커밋보다 먼저 출력'되도록 정렬된 커밋 리스트를 반환합니다.

        시간복잡도: O((V + E) log V) - 진입차수가 0인 후보들 간 생성 순서(seq) 정렬 포함
        """
        in_degree: Dict[str, int] = {}
        for c_hash, commit in self.commits.items():
            # 부모 중 현재 그래프에 존재하는 수만큼 진입차수 설정
            in_degree[c_hash] = len(commit.parents)

        # 진입차수가 0인 루트 커밋 수집
        ready: List[Commit] = [
            self.commits[c_hash]
            for c_hash, deg in in_degree.items()
            if deg == 0
        ]
        ready = Sorter.merge_sort(ready, key=lambda c: (c.seq, c.hash))

        result: List[Commit] = []
        while ready:
            current = ready.pop(0)
            result.append(current)

            newly_ready: List[Commit] = []
            for child_hash in self.children_map.get(current.hash, []):
                in_degree[child_hash] -= 1
                if in_degree[child_hash] == 0:
                    newly_ready.append(self.commits[child_hash])

            if newly_ready:
                ready = Sorter.merge_sort(
                    ready + newly_ready,
                    key=lambda c: (c.seq, c.hash),
                )

        return result

    def find_shortest_path(self, start_hash: str, end_hash: str) -> Optional[List[str]]:
        """
        두 커밋 사이의 최단 경로를 탐색합니다 (BFS 기반).
        - 커밋-부모 연결을 무방향 간선으로 간주합니다.
        - 최단 경로(간선 수 최소)가 여러 개일 경우,
          'hash1->hash2->...' 문자열 기준 사전순이 가장 작은 경로를 선택합니다.

        시간복잡도: O(V + E)
        """
        if start_hash not in self.commits:
            raise ValueError(f"Unknown commit: {start_hash}")
        if end_hash not in self.commits:
            raise ValueError(f"Unknown commit: {end_hash}")

        if start_hash == end_hash:
            return [start_hash]

        # 무방향 이웃 목록 반환 헬퍼
        def get_neighbors(c_hash: str) -> List[str]:
            commit = self.commits[c_hash]
            neighbors_set: Set[str] = set(commit.parents) | set(self.children_map.get(c_hash, []))
            return Sorter.merge_sort(list(neighbors_set))

        # 각 노드까지의 최단 거리(dist)와 해당 최단 거리에 도달하는 모든 경로 목록을 유지하는 BFS
        dist: Dict[str, int] = {start_hash: 0}
        shortest_paths: Dict[str, List[List[str]]] = {start_hash: [[start_hash]]}
        queue: deque[str] = deque([start_hash])

        while queue:
            curr = queue.popleft()
            curr_dist = dist[curr]
            curr_paths = shortest_paths[curr]

            # 이미 목표 노드의 최단 거리를 찾았고, 현재 깊이가 그 이상이면 더 탐색할 필요 없음
            if end_hash in dist and curr_dist >= dist[end_hash]:
                continue

            for nxt in get_neighbors(curr):
                if nxt not in dist:
                    dist[nxt] = curr_dist + 1
                    shortest_paths[nxt] = [p + [nxt] for p in curr_paths]
                    queue.append(nxt)
                elif dist[nxt] == curr_dist + 1:
                    for p in curr_paths:
                        candidate_path = p + [nxt]
                        if candidate_path not in shortest_paths[nxt]:
                            shortest_paths[nxt].append(candidate_path)

        if end_hash not in shortest_paths:
            return None

        # 최단 경로가 여러 개일 경우 'hash1->hash2->...' 문자열 기준 사전순 최소 경로 선택
        candidates = shortest_paths[end_hash]
        ordered_candidates = Sorter.merge_sort(candidates, key=lambda p: "->".join(p))
        return ordered_candidates[0]

    def find_ancestors(self, commit_hash: str) -> List[Commit]:
        """
        특정 커밋에서 도달 가능한 모든 조상 커밋을 탐색하여 반환합니다 (BFS/DFS).
        자신(commit_hash)을 제외한 모든 선조 커밋을 빠짐없이 수집하며,
        인과 순서(위상/생성 순)에 맞춰 반환합니다.

        시간복잡도: O(V + E)
        """
        if commit_hash not in self.commits:
            raise ValueError(f"Unknown commit: {commit_hash}")

        visited: Set[str] = set()
        queue: deque[str] = deque(self.commits[commit_hash].parents)

        while queue:
            curr_hash = queue.popleft()
            if curr_hash in visited:
                continue
            visited.add(curr_hash)
            curr_commit = self.commits[curr_hash]
            for p_hash in curr_commit.parents:
                if p_hash not in visited:
                    queue.append(p_hash)

        ancestor_commits = [self.commits[h] for h in visited]
        return Sorter.merge_sort(ancestor_commits, key=lambda c: (c.seq, c.hash))


# =====================================================================
# 3. 역색인 모듈 (Inverted Index)
# =====================================================================

class InvertedIndex:
    """
    커밋 검색 속도를 높이기 위한 역색인(Inverted Index) 클래스.
    전체 커밋을 순회(O(N))하지 않고 해시 테이블 조회를 통해 후보 커밋 해시 목록을 즉시(O(1)) 가져옵니다.
    - keyword_index: 소문자 정규화된 토큰 -> 커밋 해시 리스트
    - author_index: 작성자 이름(원본 및 소문자) -> 커밋 해시 리스트
    """

    def __init__(self) -> None:
        self.keyword_index: Dict[str, List[str]] = {}
        self.author_index: Dict[str, List[str]] = {}

    def clear(self) -> None:
        """인덱스를 초기화합니다."""
        self.keyword_index.clear()
        self.author_index.clear()

    @staticmethod
    def extract_keywords(message: str) -> List[str]:
        """
        커밋 메시지를 공백 기준으로 분리(split)하고 소문자(lower)로 정규화한 토큰을 추출합니다.
        구두점이 붙은 단어 검색 편의를 위해 양끝 구두점을 제거한 토큰도 함께 색인합니다.
        """
        raw_tokens = message.split()
        tokens: List[str] = []
        for raw in raw_tokens:
            lowered = raw.lower()
            if lowered and lowered not in tokens:
                tokens.append(lowered)
            stripped = lowered.strip(".,!?;:\"'()[]{}")
            if stripped and stripped not in tokens:
                tokens.append(stripped)
        return tokens

    def index_commit(self, commit: Commit) -> None:
        """새 커밋이 생성될 때 작성자 및 키워드 역색인을 갱신합니다."""
        # 1. 키워드 역색인 갱신
        for token in self.extract_keywords(commit.message):
            if token not in self.keyword_index:
                self.keyword_index[token] = []
            if commit.hash not in self.keyword_index[token]:
                self.keyword_index[token].append(commit.hash)

        # 2. 작성자 역색인 갱신 (대소문자 무관 검색을 위해 소문자 키로 정규화 저장)
        author_key = commit.author.lower()
        if author_key not in self.author_index:
            self.author_index[author_key] = []
        if commit.hash not in self.author_index[author_key]:
            self.author_index[author_key].append(commit.hash)

    def search_by_keyword(self, keyword: str) -> List[str]:
        """키워드 역색인에서 O(1)로 커밋 해시 목록을 조회합니다."""
        normalized = keyword.strip().lower()
        if not normalized:
            return []
        # 여러 단어 키워드가 들어온 경우 교집합 처리
        parts = normalized.split()
        if len(parts) == 1:
            return list(self.keyword_index.get(parts[0], []))

        first_hits = list(self.keyword_index.get(parts[0], []))
        rest_sets = [set(self.keyword_index.get(p, [])) for p in parts[1:]]
        return [h for h in first_hits if all(h in s for s in rest_sets)]

    def search_by_author(self, author: str) -> List[str]:
        """작성자 역색인에서 O(1)로 커밋 해시 목록을 조회합니다."""
        normalized = author.strip().lower()
        return list(self.author_index.get(normalized, []))


# =====================================================================
# 4. 파일 비교 모듈 (보너스 과제: LCS 기반 줄 단위 Diff)
# =====================================================================

class DiffEngine:
    """
    두 텍스트 파일을 줄 단위로 비교하여 추가(+), 삭제(-), 공통( ) 줄을 출력하는 클래스.
    동적 계획법(Dynamic Programming) 기반의 LCS(Longest Common Subsequence) 알고리즘을 사용합니다.
    """

    @staticmethod
    def diff_lines(lines_a: List[str], lines_b: List[str]) -> List[str]:
        """두 문자열 리스트를 비교하여 줄 단위 diff 결과를 생성합니다."""
        m, n = len(lines_a), len(lines_b)
        dp: List[List[int]] = [[0] * (n + 1) for _ in range(m + 1)]

        for i in range(m - 1, -1, -1):
            for j in range(n - 1, -1, -1):
                if lines_a[i] == lines_b[j]:
                    dp[i][j] = 1 + dp[i + 1][j + 1]
                else:
                    dp[i][j] = dp[i + 1][j] if dp[i + 1][j] >= dp[i][j + 1] else dp[i][j + 1]

        result: List[str] = []
        i, j = 0, 0
        while i < m and j < n:
            if lines_a[i] == lines_b[j]:
                result.append(f"  {lines_a[i]}")
                i += 1
                j += 1
            elif dp[i + 1][j] >= dp[i][j + 1]:
                result.append(f"- {lines_a[i]}")
                i += 1
            else:
                result.append(f"+ {lines_b[j]}")
                j += 1

        while i < m:
            result.append(f"- {lines_a[i]}")
            i += 1
        while j < n:
            result.append(f"+ {lines_b[j]}")
            j += 1

        return result

    @staticmethod
    def diff_files(file1: str, file2: str) -> str:
        """두 텍스트 파일을 읽어 줄 단위 비교 결과를 문자열로 반환합니다."""
        try:
            with open(file1, "r", encoding="utf-8") as f1:
                lines_a = [line.rstrip("\r\n") for line in f1.readlines()]
        except OSError as exc:
            raise ValueError(f"Cannot read file '{file1}': {exc}") from exc

        try:
            with open(file2, "r", encoding="utf-8") as f2:
                lines_b = [line.rstrip("\r\n") for line in f2.readlines()]
        except OSError as exc:
            raise ValueError(f"Cannot read file '{file2}': {exc}") from exc

        header = [f"--- {file1}", f"+++ {file2}"]
        body = DiffEngine.diff_lines(lines_a, lines_b)
        return "\n".join(header + body)


# =====================================================================
# 5. Mini Git 저장소 엔진 (Repository Manager)
# =====================================================================

class MiniGitRepository:
    """
    저장소 초기화, 브랜치 생성/전환/병합, 커밋 생성, 로그, 탐색, 검색을 총괄하는 클래스.
    """

    def __init__(self) -> None:
        self.initialized: bool = False
        self.current_user: Optional[str] = None
        self.current_branch: Optional[str] = None
        # branch_name -> commit_hash (커밋이 아직 없으면 None)
        self.branches: Dict[str, Optional[str]] = {}
        self.graph: CommitGraph = CommitGraph()
        self.index: InvertedIndex = InvertedIndex()

    def _ensure_initialized(self) -> None:
        if not self.initialized:
            raise ValueError("Repository is not initialized. Please run 'INIT <user_name>' first.")

    def init(self, user_name: str) -> str:
        """
        INIT <user_name>
        저장소 초기화, main 브랜치 생성 및 HEAD 설정, 현재 사용자 설정
        """
        if not user_name.strip():
            raise ValueError("Invalid args")

        self.initialized = True
        self.current_user = user_name
        self.current_branch = "main"
        self.branches = {"main": None}
        self.graph.clear()
        self.index.clear()

        return (
            "Initialized repository.\n"
            f"Current branch: {self.current_branch}\n"
            f"Current user: {self.current_user}"
        )

    def user(self, user_name: str) -> str:
        """현재 작업 사용자(author)를 변경하는 편의 기능."""
        self._ensure_initialized()
        if not user_name.strip():
            raise ValueError("Invalid args")
        self.current_user = user_name
        return f"Current user set to: {self.current_user}"

    def branch(self, branch_name: str) -> str:
        """
        BRANCH <branch_name>
        현재 커밋(HEAD)을 가리키는 새 브랜치 생성
        """
        self._ensure_initialized()
        if not branch_name.strip():
            raise ValueError("Invalid args")
        if branch_name in self.branches:
            raise ValueError(f"Branch already exists: {branch_name}")

        head_commit = self.branches[self.current_branch]  # type: ignore[index]
        self.branches[branch_name] = head_commit
        return f"Created branch: {branch_name}"

    def switch(self, branch_name: str) -> str:
        """
        SWITCH <branch_name>
        HEAD를 지정한 브랜치로 이동
        """
        self._ensure_initialized()
        if branch_name not in self.branches:
            raise ValueError(f"Unknown branch: {branch_name}")

        self.current_branch = branch_name
        return f"Switched to branch: {branch_name}"

    def commit(self, message: str, timestamp: Optional[str] = None) -> str:
        """
        COMMIT <message>
        현재 HEAD를 부모로 하는 새 커밋 생성 및 역색인 갱신
        """
        self._ensure_initialized()
        if not message.strip():
            raise ValueError("Invalid args")

        assert self.current_branch is not None
        assert self.current_user is not None

        head_hash = self.branches[self.current_branch]
        parents = [head_hash] if head_hash is not None else []

        new_commit = self.graph.add_commit(
            message=message,
            author=self.current_user,
            parents=parents,
            timestamp=timestamp,
        )
        self.branches[self.current_branch] = new_commit.hash
        self.index.index_commit(new_commit)

        return f"[{self.current_branch} {new_commit.hash}] {new_commit.message}"

    def merge(self, target_branch: str) -> str:
        """
        보너스 과제: MERGE <branch_name>
        현재 브랜치의 HEAD와 대상 브랜치의 HEAD를 부모(2개)로 가지는 merge commit 생성
        """
        self._ensure_initialized()
        if target_branch not in self.branches:
            raise ValueError(f"Unknown branch: {target_branch}")

        assert self.current_branch is not None
        assert self.current_user is not None

        if target_branch == self.current_branch:
            raise ValueError("Cannot merge a branch into itself.")

        current_head = self.branches[self.current_branch]
        target_head = self.branches[target_branch]

        if current_head is None or target_head is None:
            raise ValueError("Cannot merge branches without commits.")

        if current_head == target_head:
            return f"Already up to date with {target_branch}."

        message = f"Merge branch '{target_branch}' into {self.current_branch}"
        merge_commit = self.graph.add_commit(
            message=message,
            author=self.current_user,
            parents=[current_head, target_head],
        )
        self.branches[self.current_branch] = merge_commit.hash
        self.index.index_commit(merge_commit)

        return (
            f"[{self.current_branch} {merge_commit.hash}] {merge_commit.message} "
            f"(parents: {current_head}, {target_head})"
        )

    def _format_commit_for_log(self, commit: Commit, show_branches: bool = True) -> str:
        branch_tags: List[str] = []
        if show_branches:
            for b_name, b_head in self.branches.items():
                if b_head == commit.hash:
                    branch_tags.append(b_name)
            branch_tags = Sorter.merge_sort(branch_tags)

        tag_str = ""
        if branch_tags:
            tag_str = " " + " ".join(f"[{b}]" for b in branch_tags)

        parent_info = ""
        if len(commit.parents) > 1:
            parent_info = f"\nMerge: {' '.join(commit.parents)}"

        return (
            f"commit {commit.hash} ({commit.author}, {commit.timestamp}){tag_str}"
            f"{parent_info}\n"
            f"{commit.message}"
        )

    def log(self, sort_by: Optional[str] = None) -> str:
        """
        LOG 및 LOG --sort-by=date|author
        - 기본 LOG: 부모 커밋이 항상 자식 커밋보다 먼저 출력되는 위상 정렬(Topological Sort) 출력
        - --sort-by=date: timestamp 기준 정렬 (직접 구현한 Merge Sort 사용)
        - --sort-by=author: author 이름 기준 정렬 (직접 구현한 Merge Sort 사용)
        """
        self._ensure_initialized()
        if not self.graph.commits:
            return "No commits yet."

        if sort_by is None:
            ordered = self.graph.topological_sort()
            return "\n".join(self._format_commit_for_log(c, show_branches=True) for c in ordered)

        sort_by_lower = sort_by.lower()
        all_commits = list(self.graph.commits.values())

        if sort_by_lower == "date":
            ordered = Sorter.merge_sort(all_commits, key=lambda c: (c.timestamp, c.seq))
        elif sort_by_lower == "author":
            ordered = Sorter.merge_sort(all_commits, key=lambda c: (c.author.lower(), c.timestamp, c.seq))
        else:
            raise ValueError("Invalid args")

        return "\n".join(self._format_commit_for_log(c, show_branches=False) for c in ordered)

    def path(self, commit1: str, commit2: str) -> str:
        """
        PATH <commit1> <commit2>
        커밋-부모 간선을 무방향으로 간주했을 때의 최단 경로 탐색
        """
        self._ensure_initialized()
        shortest = self.graph.find_shortest_path(commit1, commit2)
        if not shortest:
            return "No path"
        return "Path: " + " -> ".join(shortest)

    def ancestors(self, commit_hash: str) -> str:
        """
        ANCESTORS <commit_hash>
        해당 커밋에서 도달 가능한 모든 조상 커밋 출력
        """
        self._ensure_initialized()
        ancestor_list = self.graph.find_ancestors(commit_hash)
        if not ancestor_list:
            return f"No ancestors found for {commit_hash}."

        lines = [f"Ancestors of {commit_hash} ({len(ancestor_list)}):"]
        for c in ancestor_list:
            lines.append(f"- {c.hash} ({c.author}, {c.timestamp}): {c.message}")
        return "\n".join(lines)

    def search(self, keyword: Optional[str] = None, author: Optional[str] = None) -> str:
        """
        SEARCH <keyword> 또는 SEARCH --author=<name>
        역색인 기반으로 커밋을 빠르게 조회하여 출력
        """
        self._ensure_initialized()
        if author is not None:
            hashes = self.index.search_by_author(author)
        elif keyword is not None:
            hashes = self.index.search_by_keyword(keyword)
        else:
            raise ValueError("Invalid args")

        if not hashes:
            return "Found 0 commits."

        commits = [self.graph.commits[h] for h in hashes if h in self.graph.commits]
        commits = Sorter.merge_sort(commits, key=lambda c: (c.seq, c.hash))

        count = len(commits)
        noun = "commit" if count == 1 else "commits"
        lines = [f"Found {count} {noun}:\n"]
        for c in commits:
            lines.append(f"- {c.hash}: {c.message}")
        return "\n".join(lines)


# =====================================================================
# 6. CLI 파서 및 REPL 인터페이스 (MiniGitCLI)
# =====================================================================

class MiniGitCLI:
    """
    mini-git> 프롬프트에서 명령을 입력받아 파싱 및 실행하는 REPL 인터페이스 클래스.
    """

    def __init__(self) -> None:
        self.repo = MiniGitRepository()

    def execute_line(self, line: str) -> Optional[str]:
        """
        한 줄의 CLI 명령어를 파싱하고 실행 결과를 반환합니다.
        종료 명령(exit/quit)인 경우 SystemExit를 발생시킵니다.
        """
        stripped = line.strip()
        if not stripped:
            return None

        try:
            tokens = shlex.split(stripped)
        except ValueError:
            return "Invalid args"

        if not tokens:
            return None

        cmd = tokens[0].upper()
        args = tokens[1:]

        try:
            if cmd in ("EXIT", "QUIT"):
                raise SystemExit(0)

            elif cmd == "INIT":
                if len(args) != 1:
                    return "Invalid args"
                return self.repo.init(args[0])

            elif cmd == "USER":
                if len(args) != 1:
                    return "Invalid args"
                return self.repo.user(args[0])

            elif cmd == "BRANCH":
                if len(args) != 1:
                    return "Invalid args"
                return self.repo.branch(args[0])

            elif cmd == "SWITCH":
                if len(args) != 1:
                    return "Invalid args"
                return self.repo.switch(args[0])

            elif cmd == "COMMIT":
                if len(args) != 1:
                    return "Invalid args"
                return self.repo.commit(args[0])

            elif cmd == "MERGE":
                if len(args) != 1:
                    return "Invalid args"
                return self.repo.merge(args[0])

            elif cmd == "LOG":
                if len(args) == 0:
                    return self.repo.log()
                elif len(args) == 1 and args[0].lower().startswith("--sort-by="):
                    sort_key = args[0].split("=", 1)[1]
                    if sort_key.lower() not in ("date", "author"):
                        return "Invalid args"
                    return self.repo.log(sort_by=sort_key)
                else:
                    return "Invalid args"

            elif cmd == "PATH":
                if len(args) != 2:
                    return "Invalid args"
                return self.repo.path(args[0], args[1])

            elif cmd == "ANCESTORS":
                if len(args) != 1:
                    return "Invalid args"
                return self.repo.ancestors(args[0])

            elif cmd == "SEARCH":
                if len(args) != 1:
                    return "Invalid args"
                arg = args[0]
                if arg.lower().startswith("--author="):
                    author_name = arg.split("=", 1)[1]
                    if not author_name:
                        return "Invalid args"
                    return self.repo.search(author=author_name)
                elif arg.startswith("--"):
                    return "Invalid args"
                else:
                    return self.repo.search(keyword=arg)

            elif cmd == "DIFF":
                if len(args) != 2:
                    return "Invalid args"
                return DiffEngine.diff_files(args[0], args[1])

            elif cmd == "BENCHMARK":
                if len(args) == 0:
                    return Sorter.benchmark()
                try:
                    sizes = [int(a) for a in args]
                    if any(s <= 0 for s in sizes):
                        return "Invalid args"
                    return Sorter.benchmark(sizes)
                except ValueError:
                    return "Invalid args"

            elif cmd == "HELP":
                return self._help_message()

            else:
                return f"Invalid args: Unknown command '{tokens[0]}'"

        except ValueError as exc:
            return str(exc)

    @staticmethod
    def _help_message() -> str:
        return (
            "Available commands:\n"
            "  INIT <user_name>             Initialize repository and set current user\n"
            "  BRANCH <branch_name>         Create a new branch at current HEAD\n"
            "  SWITCH <branch_name>         Switch HEAD to the specified branch\n"
            "  COMMIT <message>             Create a new commit on the current branch\n"
            "  MERGE <branch_name>          Merge specified branch into current branch (Bonus)\n"
            "  LOG                          Show commits in topological order (parent before child)\n"
            "  LOG --sort-by=date|author    Show commits ordered by timestamp or author\n"
            "  PATH <commit1> <commit2>     Find shortest undirected path between two commits\n"
            "  ANCESTORS <commit_hash>      Show all reachable ancestor commits\n"
            "  SEARCH <keyword>             Search commits by message keyword (Inverted Index)\n"
            "  SEARCH --author=<name>       Search commits by author name (Inverted Index)\n"
            "  DIFF <file1> <file2>         Compare two files line by line (Bonus)\n"
            "  BENCHMARK [n1 n2 ...]        Compare custom sorting algorithms (Bonus)\n"
            "  EXIT / QUIT                  Exit Mini Git REPL"
        )

    def run_repl(self) -> None:
        """표준 입력으로부터 명령을 반복해서 읽고 실행하는 REPL 루프."""
        while True:
            try:
                line = input("mini-git> ")
            except EOFError:
                print()
                break
            except KeyboardInterrupt:
                print()
                break

            try:
                output = self.execute_line(line)
                if output is not None:
                    print(output)
            except SystemExit:
                break


def main() -> None:
    cli = MiniGitCLI()
    cli.run_repl()


if __name__ == "__main__":
    main()
