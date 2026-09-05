Feature: Hourly request rate limiter

  Scenario: Allow actions while under the hourly cap
    Given a rate limiter allowing 3 actions per hour
    When 2 actions are recorded
    Then one more action is allowed

  Scenario: Deny actions once the hourly cap is reached
    Given a rate limiter allowing 3 actions per hour
    When 3 actions are recorded
    Then one more action is not allowed

  Scenario: Allow actions again once the window has fully elapsed
    Given a rate limiter allowing 3 actions per hour
    When 3 actions are recorded
    And 3601 seconds pass
    Then one more action is allowed
