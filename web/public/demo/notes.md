## What Is Binary Search?

![Binary Search Algorithm Diagram](https://media.geeksforgeeks.org/wp-content/uploads/20240506155201/binnary-search-.webp)
*Caption: Step-by-step visualization of binary search narrowing down to a target element.*

- A **divide-and-conquer** search algorithm that locates a target value in a **sorted** collection by repeatedly halving the search space.
- Compares the target to the **middle element**; discards the half that cannot contain the target.
- Sourced from Wikipedia: requires only three pointers (low, high, mid), keeping **space usage minimal** regardless of array size.
- Far more efficient than linear search for large datasets — O(log n) vs O(n).

**Example:** Searching for `7` in `[2, 3, 5, 7, 8, 10, 12]` — mid is `7` (index 3), found on the **first comparison**.

---

## Preconditions & Core Mechanics

![Sorted Array Binary Search](https://www.geeksforgeeks.org/wp-content/uploads/Binary-Search.png)
*Caption: Binary search requires a fully sorted array before the first comparison.*

- **Precondition:** The array **must be sorted** (ascending or descending); results are undefined otherwise.
- Three pointers maintained each step: `low = 0`, `high = n-1`, `mid = (low + high) / 2`.
- **Three outcomes** each iteration:
  - `arr[mid] == target` → found, return index.
  - `arr[mid] < target` → move `low = mid + 1` (search right half).
  - `arr[mid] > target` → move `high = mid - 1` (search left half).
- Loop terminates when `low > high` (target absent → return -1).

**Example:** Target `10` in `[1, 3, 5, 7, 10, 14, 18]`: mid=`7`(too small) → mid=`14`(too big) → mid=`10` ✓ (3 steps).

---

## Iterative vs. Recursive Implementation

![Binary Search Flowchart](https://image2.slideserve.com/4444251/binary-search-flowchart-l.jpg)
*Caption: Flowchart comparing the decision logic used in binary search iterations.*

- **Iterative** approach uses a `while (low <= high)` loop — preferred for its **O(1) space** usage.
- **Recursive** approach calls itself with updated bounds — elegant but adds **O(log n) call-stack frames**.
- Both yield identical O(log n) **time complexity** per GeeksforGeeks and TechieDelight sources.

**Example (Python — Iterative):**
```python
def binary_search(arr, target):
    low, high = 0, len(arr) - 1
    while low <= high:
        mid = (low + high) // 2
        if arr[mid] == target: return mid
        elif arr[mid] < target: low = mid + 1
        else: high = mid - 1
    return -1
```

---

## Time & Space Complexity

![Binary Search Time Complexity Graph](https://www.w3schools.com/dsa/img_binarysearch_timecomplexity.png)
*Caption: O(log n) grows extremely slowly compared to O(n), making binary search highly scalable.*

- **Best case:** O(1) — target is the first mid element checked.
- **Average & Worst case:** **O(log n)** — array is halved each step; 1,000,000 elements need ≤ 20 comparisons.
- **Space complexity:** O(1) iterative / O(log n) recursive (call stack).
- Per FreeCodeCamp: for n = 1,000 elements, binary search needs ≤ 10 comparisons vs. up to 1,000 for linear search.

**Example:** An array of 1 billion elements requires at most **⌈log₂(10⁹)⌉ = 30** comparisons.

---

## Common Pitfalls & Edge Cases

![Integer Overflow in Binary Search](https://miro.medium.com/v2/resize:fit:1024/1*NsLBNICoFGiP9ZfYNttPaA.png)
*Caption: Integer overflow when computing mid is a classic binary search bug in languages with fixed-width integers.*

- **Integer overflow:** `mid = (low + high) / 2` can overflow in languages like C/Java; use `mid = low + (high - low) / 2` instead.
- **Off-by-one errors:** Incorrectly using `<` instead of `<=` in the loop condition causes missed elements.
- **Unsorted input:** Binary search silently produces wrong answers on unsorted arrays.
- **Duplicate elements:** Standard binary search may return any matching index; use modified versions to find first/last occurrence.
- **Empty arrays:** Always guard with an initial `if len(arr) == 0` check.

**Example:** With `low=2_000_000_000` and `high=2_100_000_000` in Java (32-bit int), `(low+high)` overflows; safe formula prevents this.

---

## Real-World Applications

![Binary Search Real World Applications](https://www.kaashivinfotech.com/blog/wp-content/uploads/2025/08/Real-World-Applications-of-Binary-Search.webp)
*Caption: Binary search powers everything from database indexing to system-level library functions.*

- **Standard libraries:** Python's `bisect`, Java's `Arrays.binarySearch()`, C++'s `std::binary_search` all use it.
- **Database indexing:** B-trees extend binary search logic for fast record lookup.
- **Git bisect:** Finds the commit that introduced a bug by binary-searching commit history.
- **Numeric methods:** Used to find square roots, solve monotonic equations, and in "binary search on the answer" competitive programming technique.
- **Networking:** IP routing tables use binary search for longest-prefix matching.

**Example:** `bisect.bisect_left([1,3,5,7,9], 6)` returns index `3` — the insertion point — in O(log n) time.