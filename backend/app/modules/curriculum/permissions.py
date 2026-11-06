"""Permission codes owned by the curriculum module and their default role grants."""

COURSE_VIEW = "course.view"
COURSE_MANAGE = "course.manage"
ACTIVITY_SUBMIT = "activity.submit"
ACTIVITY_REVIEW = "activity.review"

PERMISSIONS = {
    COURSE_VIEW: "View assigned courses and lessons",
    COURSE_MANAGE: "Create and edit courses, modules, lessons and activities",
    ACTIVITY_SUBMIT: "Complete and submit learning activities",
    ACTIVITY_REVIEW: "Review submitted activities",
}
DEFAULT_GRANTS = {
    "INSTRUCTOR": [COURSE_VIEW, COURSE_MANAGE, ACTIVITY_REVIEW],
    "STUDENT": [COURSE_VIEW, ACTIVITY_SUBMIT],
}
