// ...existing code...
#include <stdio.h>
#include <string.h>
#include <stdlib.h>

#define MAX_CANDIDATES 10
#define MAX_NAME 64
#define INPUT_BUF 128

typedef struct { //changes
    char name[MAX_NAME];
    int votes;
} Candidate;

static Candidate candidates[MAX_CANDIDATES];
static int candidate_count = 0;

static void strip_newline(char *s) {
    size_t n = strlen(s);
    if (n && s[n-1] == '\n') s[n-1] = '\0';
}

static void add_candidate(void) {
    if (candidate_count >= MAX_CANDIDATES) {
        printf("Maximum number of candidates reached (%d).\n", MAX_CANDIDATES);
        return;
    }
    char buf[INPUT_BUF];
    printf("Enter candidate name: ");
    if (!fgets(buf, sizeof(buf), stdin)) return;
    strip_newline(buf);
    if (strlen(buf) == 0) {
        printf("Name cannot be empty.\n");
        return;
    }
    strncpy(candidates[candidate_count].name, buf, MAX_NAME-1);
    candidates[candidate_count].name[MAX_NAME-1] = '\0';
    candidates[candidate_count].votes = 0;
    candidate_count++;
    printf("Candidate added: %s\n", buf);
}

static void list_candidates(void) {
    if (candidate_count == 0) {
        printf("No candidates registered.\n");
        return;
    }
    printf("Candidates:\n");
    for (int i = 0; i < candidate_count; ++i) {
        printf("  %d) %s (votes: %d)\n", i+1, candidates[i].name, candidates[i].votes);
    }
}

static void cast_vote(void) {
    if (candidate_count == 0) {
        printf("No candidates to vote for. Add candidates first.\n");
        return;
    }
    list_candidates();
    char buf[INPUT_BUF];
    printf("Enter candidate number to vote for (or 0 to cancel): ");
    if (!fgets(buf, sizeof(buf), stdin)) return;
    int choice = atoi(buf);
    if (choice <= 0) {
        printf("Vote cancelled.\n");
        return;
    }
    if (choice < 1 || choice > candidate_count) {
        printf("Invalid candidate number.\n");
        return;
    }
    candidates[choice-1].votes++;
    printf("Vote cast for %s\n", candidates[choice-1].name);
}

static void display_results(void) {
    if (candidate_count == 0) {
        printf("No candidates registered.\n");
        return;
    }
    int total = 0;
    for (int i = 0; i < candidate_count; ++i) total += candidates[i].votes;

    printf("Results:\n");
    for (int i = 0; i < candidate_count; ++i) {
        double pct = total ? (candidates[i].votes * 100.0 / total) : 0.0;
        printf("  %s: %d votes (%.2f%%)\n", candidates[i].name, candidates[i].votes, pct);
    }

    if (total == 0) {
        printf("No votes cast yet.\n");
        return;
    }

    int max_votes = 0;
    for (int i = 0; i < candidate_count; ++i)
        if (candidates[i].votes > max_votes) max_votes = candidates[i].votes;

    printf("Winner(s):\n");
    for (int i = 0; i < candidate_count; ++i)
        if (candidates[i].votes == max_votes)
            printf("  %s\n", candidates[i].name);
}

static void reset_election(void) {
    for (int i = 0; i < candidate_count; ++i) {
        candidates[i].votes = 0;
        candidates[i].name[0] = '\0';
    }
    candidate_count = 0;
    printf("Election reset. All candidates removed.\n");
}

int main(void) {
    char buf[INPUT_BUF];
    for (;;) {
        printf("\n--- Interactive Voting System ---\n");
        printf("1) Add candidate\n");
        printf("2) List candidates\n");
        printf("3) Cast vote\n");
        printf("4) Show results\n");
        printf("5) Reset election\n");
        printf("0) Exit\n");
        printf("Select option: ");
        if (!fgets(buf, sizeof(buf), stdin)) break;
        int opt = atoi(buf);
        switch (opt) {
            case 1: add_candidate(); break;
            case 2: list_candidates(); break;
            case 3: cast_vote(); break;
            case 4: display_results(); break;
            case 5: reset_election(); break;
            case 0:
                printf("Exiting.\n");
                return 0;
            default:
                printf("Invalid option.\n");
        }
    }
    return 0;
}
// ...existing code...