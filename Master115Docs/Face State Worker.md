# Introduction

We will create a new `./master115/models/face_state_worker.py` that will replace our old face_swap_worker.py by stages.

In this new state machine worker:
- the error handling will only report the errors and not do heavy lifting work.
- All logs must be reported using both logger.xxx() (where "xxx" is log level) and log_message.emit() to be consistant. Each logs must show the module name and the worker's ID and a descriptive step identifier.
- All "timeout related" errors or events will be reported with both logger.debug() and log_message.emit(). No traceback print out necessarily.
- Each worker must cleanup their browser instance before quiting
- Before each step of the process (and in the respective helper function), the worker must check for User Stop signal (user clicks on the Start/Stop button in the face_dashboard page)

# Clarifications on the Approach

*   **State Variable (`_need_refresh`):** The core of the state machine. When set to `True`, it indicates that the browser/page state is potentially inconsistent (due to a previous error, timeout, or specific condition like the 'Too Many Requests' popup). The main loop checks this flag at the beginning of each source image processing cycle and triggers recovery actions (`_guarantee_fresh_pixnova`) if needed before proceeding.
*   **"Guarantee" Functions (`_guarantee_xxx`):** These helper functions encapsulate the logic required to ensure a specific precondition is met (e.g., browser is running, page is loaded, face image is uploaded). They contain their own internal retry loops (`while True`) to handle transient errors until the condition is met or a stop signal is received. They simplify the main `run` loop by abstracting away these retry mechanisms.
*   **Simplified Error Handling:** Unlike the previous worker's complex nested retries, helper functions in this design generally focus on achieving their specific goal. If they encounter an error they cannot immediately resolve within their retry loop (or if it's a non-recoverable state), they log the error and return a failure status (e.g., `False`). The main `run` loop then interprets this failure and typically sets `_need_refresh = True`, relying on the state mechanism for recovery in the *next* iteration, rather than handling complex recovery within the failing function itself.
*   **Logging Strategy:** Every significant action or check will generate two logs: one using `self.logger` (for terminal/file output) and one using `self.log_message.emit()` (for the UI status display). Logs will include the worker's unique ID and a step identifier (e.g., `[guarantee_pixnova][attempt_1]`) instead of fragile line numbers, aiding debuggability.
*   **Stop Signal Handling:** Stop signal checks (`if self.stop_event.is_set(): ...`) are implemented at the beginning of major loops and before potentially long-running operations to allow for reasonably timely graceful shutdowns when requested by the user.

# Pseudo Code

Here's the high level pseudo code for our new state worker:

class FaceStateWorker(QObject): 
    # ... other standard worker functions goes here...
    
    def run():
    Do necessary initializations

    self.browser = create_browser()
    # at this point, we are guaranteed a valid self.browser
    self.guarantee_pixnova()
    # at this point, self.browser is guaranteed to be on pixnova site

    self._need_refresh = false
    self._current_source_image = get_next_source_image()

    while self._current_source_image:
        try:
        if self._need_refresh:
            while not self.guarantee_fresh_pixnova():
            log browser failure
            kill_browser_and_start_new_guaranteed_brower()
            self._need_refresh = false

        face_image_status = self._check_face_image_presence()
        if not face_image_status:
            self.guarantee_face_upload()

        # here, we are guaranteed at least a valid face image
        source_result = self.guarantee_source_upload()
        if not source_result:
            # we got stuck during source image upload
            self._need_refresh = true
            contine to next iteration of while loop

        # here, we are guaranteed face + source images
        start_button = self._get_faceswap_start_button(...)
        if (not start_button) or (start_button status is not enabled):
            self._need_refresh = true
            sleep(3 seconds)
            contine to next iteration of while loop

        faceswap_result = self._start_faceswap(...)
        if not faceswap_result:
            self._need_refresh = true
        else:
            save the face swap image result
            signal the manager of job completion
            make appropriate logs
            self._current_source_image = get_next_source_image()
            log next job starting or log worker done

        except Some Exception:
        if it's timeout, log it as debug and continue next iteration
        else log the error mesg with trackback and continue
        finally:
        cleanup()

        # all jobs done
        cleanup_more_optional()
        log the worker's exiting  

    def guarantee_fresh_pixnova()
    try:
        clear self.browser cache and local storage
    except Some Exception:
        return false  
    self.guarantee_pixnova()
    return true

    def create_browser()
    attempt = 1
    while true:
        try:
        log driver creation attempt
        self.browser = initialize_chrome_driver(headless=self.run_headless)
        if successful:
            log the success
            return new driver
        ++attempt
        except Some Exception:
        log the exception only, don't do anything else
        sleep(0.5 sec)
        ++attempt

    def guarantee_pixnova()
    attempt = 1
    while true:
        try:
        log navigation attempt
        navigate to pixnova face swap site
        if successful:
            log the success
            return 
        ++attempt
        except Some Exception:
        log the exception only, don't do anything else
        ++attempt      

    def guarantee_face_upload()
    attempt = 1
    while true:
        try:
        log upload attempt
        call _upload_file_and_wait() to upload the face image

        if upload successful:
            return

        refresh the page
        ++attempt
        except Some Exception:
        log the exception only, don't do anything else
        ++attempt

    def guarantee_source_upload()
    # Here the logic is a little different from face image upload since we assume the face image already upload so we cannot refresh page

    attempt = 1
    while true:
        try:
        log upload attempt
        call _upload_file_and_wait() to upload the source image

        if upload successful:
            return true

        if source image button spinner is present:
            # here, we are considered stuck
            log failed source image upload
            return false

        source_image_button = get_source_image_upload_button()
        if source_image_button status is not enabled:
            # here, we are considered stuck
            log failed source image upload
            return false

        ++attempt  
        except Some Exception:
        log the exception only, don't do anything else
        ++attempt

    def _start_faceswap(...)
    # Here, we are guaranteed valid face+source image
    # guaranteed start button enable

    try:
        start_button = self._get_faceswap_start_button(...)
        if start_button not enabled: # safety check
        return false

        # See if there is a previously generated result first
        previous_result_image = search_result_image(RESULT_IMAGE_XPATH)
        click the start button
        sleep(1 second)
        face_swap_result = await_face_swap_result(previous_result_image)

        if face_swap_result==TOO_MANY_REQUESTS:
        sleep(3 seconds)
        # try to click only one more time
        previous_result_image = search_result_image(RESULT_IMAGE_XPATH)
        click the start button
        sleep(1 second)
        face_swap_result = await_face_swap_result(previous_result_image)
        if face_swap_result != SUCCESS:
            return false

        if face_swap_result == SUCCESS:
        return true

    except Exception:
        if error is timeout:
        log debug timeout
        else:
        log traceback stack

    return false

    def await_face_swap_result(previous_result_image)
    # Here, the start button has been clicked
    # The goal of this function is to wait and see what happens next

    prev_progress_percentage = -1
    time_percentage_update = time.time()
    start_time = time.time()
    MAX_TIMEOUT = 1 minute # applicable only if there's never a percentage found
    MAX_PERCENTAGE_TIMEOUT = 30 seconds # applicable if there's a progress percentage

    while true:
        try:
        current_result_image = search_result_image(RESULT_IMAGE_XPATH)
        if current_result_image and (current_result_image != previous_result_image):
            # we have a successful new image
            self._handle_new_success_result(current_result_image)
            return SUCCESS
        
        popup = search_too_many_requests_popup()
        if popup:
            return TOO_MANY_REQUESTS

        new_progress_percentage = search_progress_percentage(PROGRESS_PERCENTAGE_XPATH)
        if new_progress_percentage != prev_progress_percentage:
            prev_progress_percentag=new_progress_percentage
            time_percentage_update = time.time()

        if (prev_progress_percentage=-1) and (time.time()-time_percentage_update > MAX_PERCENTAGE_TIMEOUT):
            return FAILED # Progress percentage is stuck

        if (prev_progress_percentage==-1) and (time.time()-start_time > MAX_TIMEOUT):
            return FAILED # There's never a percentage, we're stuck

        sleep(1 second)

        except Some Exception:
        if exception is timeout:
            log debug the timeout
        else:
            log error and print traceback stack  
