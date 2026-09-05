Feature: LinkedIn vacancy scraper foundations

  Scenario: Build a search URL with selected filters
    Given the search filters are keyword "Python", location "Remote", remote only, and posted in the last week
    When the search URL is built
    Then the URL contains the selected LinkedIn filters

  Scenario: Persist a job only once
    Given an empty job database
    When the same job is inserted twice
    Then the database contains one job

  Scenario: Export stored jobs to CSV
    Given a database containing one job
    When the jobs are exported to a CSV file
    Then the CSV contains the job identifier and title

  Scenario: Preserve scraper statistics for reporting
    Given a scraper with statistics showing one visited page and two saved jobs
    When the scraper finishes
    Then the scraper statistics retain those values

  Scenario: Ignore internal verification markup on a normal search page
    Given a page with internal verification markup but normal visible job results
    When the page is checked for blocking
    Then the page is not considered blocked

  Scenario: Detect a visible security verification page
    Given a page with visible security verification text
    When the page is checked for blocking
    Then the page is considered blocked

  Scenario: Extract a job ID from a SPA search URL
    Given a LinkedIn search URL with current job ID "123456"
    When the job ID is extracted
    Then the extracted job ID is "123456"

  Scenario: Build a canonical job URL from a job ID
    Given a job ID "123456"
    When the canonical job URL is built
    Then the canonical job URL is "https://www.linkedin.com/jobs/view/123456/"

  Scenario: Building a canonical job URL from a missing job ID gives an empty string
    Given no job ID
    When the canonical job URL is built
    Then the canonical job URL is ""

  Scenario: Respect the requested result page count
    Given a scraper configured to scrape 2 result pages
    When the scraper page limit is read
    Then the scraper page limit is 2

  Scenario: Discover cards beyond the initially rendered viewport
    Given a results panel with 3 rendered cards and 2 more cards after scrolling
    When all result card IDs are collected
    Then 5 unique result card IDs are collected

  Scenario: Preserve the current result batch when reloading after a job
    Given a selected-job URL with result offset "25"
    When the selected-job parameter is removed
    Then the result offset remains "25"

  Scenario: Force the search region via geoId
    Given the search filters are keyword "Python", location "Remote", remote only, and posted in the last week
    And the search region is forced to "European Union"
    When the search URL is built
    Then the URL contains geoId "91000000"

  Scenario: Leave the region unforced when no region is selected
    Given the search filters are keyword "Python", location "Remote", remote only, and posted in the last week
    And the search region is not forced
    When the search URL is built
    Then the URL does not contain a geoId

  Scenario: Split a summary line into location, posted date, and applicant count
    Given a top-card summary line "Kyiv, Kyiv City, Ukraine · 2 weeks ago · 16 applicants No response insights available yet"
    When the summary line is parsed
    Then the location entity is "Kyiv, Kyiv City, Ukraine"
    And the posted date is "2 weeks ago"
    And the applicants text is "16 applicants"

  Scenario: Trim a promoted-listing tag glued onto the applicant count
    Given a top-card summary line "EMEA · 3 days ago · Over 100 applicants Promoted by hirer · No response insights available yet"
    When the summary line is parsed
    Then the location entity is "EMEA"
    And the posted date is "3 days ago"
    And the applicants text is "Over 100 applicants"

  Scenario: Recognize the "people clicked apply" variant of the applicant count
    Given a top-card summary line "Ukraine · 1 week ago · Over 100 people clicked apply Promoted by hirer · Responses managed off LinkedIn"
    When the summary line is parsed
    Then the location entity is "Ukraine"
    And the posted date is "1 week ago"
    And the applicants text is "Over 100 people clicked apply"

  Scenario: Trim trailing insight text glued directly to the applicant count
    Given a top-card summary line "EMEA · 2 months ago · 46 people clicked apply Responses managed off LinkedIn"
    When the summary line is parsed
    Then the location entity is "EMEA"
    And the posted date is "2 months ago"
    And the applicants text is "46 people clicked apply"

  Scenario: Keep a card whose title matches no skip keyword
    Given skip keywords "junior, intern, graduate" and no must-keywords
    When the title "Senior QA Engineer" is checked
    Then the card is kept

  Scenario: Skip a card whose title matches a skip keyword
    Given skip keywords "junior, intern, graduate" and no must-keywords
    When the title "Junior QA Engineer" is checked
    Then the card is skipped with reason "title-skipped"

  Scenario: Skip a card that matches no must-keyword when must-keywords are set
    Given skip keywords "junior" and must-keywords "ai, automation"
    When the title "Senior Manual QA Engineer" is checked
    Then the card is skipped with reason "no must-keyword match"

  Scenario: Keep a card that matches a must-keyword
    Given skip keywords "junior" and must-keywords "ai, automation"
    When the title "AI QA Automation Engineer" is checked
    Then the card is kept

  Scenario: Skip keywords take priority over must-keywords
    Given skip keywords "intern" and must-keywords "ai"
    When the title "AI Intern" is checked
    Then the card is skipped with reason "title-skipped"