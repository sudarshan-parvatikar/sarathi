;;; sarathi.el --- Task workspaces for resumable AI sessions -*- lexical-binding: t; -*-

;; This controller uses process APIs only.  It never injects terminal keystrokes.

(require 'json)
(require 'subr-x)
(require 'seq)
(require 'tab-bar)
(require 'comint)

(defgroup sarathi nil "Task-oriented AI workspaces." :group 'tools)

(defcustom sarathi-command "sarathi"
  "Path to the Sarathi CLI."
  :type 'string)

(defvar sarathi--tasks (make-hash-table :test #'equal))
(defvar-local sarathi-task-id nil)
(defvar-local sarathi-agent nil)

(defun sarathi--profile-environment (profile)
  "Return a process environment selecting PROFILE exactly once."
  (cons (format "SARATHI_PROFILE=%s" profile)
        (seq-remove (lambda (value) (string-prefix-p "SARATHI_PROFILE=" value))
                    process-environment)))

(defun sarathi--task-profile (task-id)
  "Return the immutable profile registered for TASK-ID."
  (or (plist-get (gethash task-id sarathi--tasks) :profile)
      (error "No Sarathi profile registered for task %s" task-id)))

(defun sarathi--label (task-id title)
  (format "%s [%s]" title (substring task-id 0 (min 8 (length task-id)))))

(defun sarathi--ensure-tab (label)
  (let ((existing (seq-find (lambda (tab) (equal (alist-get 'name tab) label))
                            (tab-bar-tabs))))
    (if existing
        (tab-bar-select-tab-by-name label)
      (tab-bar-new-tab)
      (tab-bar-rename-tab label))))

(defun sarathi--agent-buffer-name (agent task-id title)
  (format "*%s:%s [%s]*" agent title (substring task-id 0 (min 8 (length task-id)))))

(defun sarathi--rename-agent-buffers (task-id title)
  (dolist (buffer (buffer-list))
    (with-current-buffer buffer
      (when (equal sarathi-task-id task-id)
        (rename-buffer (sarathi--agent-buffer-name sarathi-agent task-id title) t)))))

(defun sarathi--split-values (value)
  "Split a semicolon-separated capture VALUE and discard blank entries."
  (seq-filter (lambda (item) (not (string-empty-p item)))
              (mapcar #'string-trim (split-string value ";"))))

(defun sarathi--flagged-values (flag values)
  (apply #'append (mapcar (lambda (value) (list flag value)) values)))

(defun sarathi-open-task (task-id workspace title profile)
  "Open or focus TASK-ID at WORKSPACE with TITLE in PROFILE."
  (interactive "sTask id: \nDWorkspace: \nsTitle: \nsProfile: ")
  (let ((label (sarathi--label task-id title)))
    (puthash task-id (list :workspace workspace :title title :profile profile)
             sarathi--tasks)
    (sarathi--ensure-tab label)
    (setq default-directory (file-name-as-directory workspace))
    (find-file (expand-file-name ".sarathi/context.md" workspace))
    (rename-frame (selected-frame) label)
    (set-frame-parameter (selected-frame) 'title label)
    (message "Sarathi focused %s" label)))

(defun sarathi--cli-json (&rest arguments)
  (with-temp-buffer
    (let ((status (apply #'call-process sarathi-command nil t nil arguments)))
      (unless (zerop status)
        (error "Sarathi command failed: %s" (string-trim (buffer-string))))
      (goto-char (point-min))
      (json-parse-buffer :object-type 'alist :array-type 'list))))

(defun sarathi-launch-agent (task-id agent)
  "Launch AGENT for TASK-ID through its supported CLI."
  (interactive
   (list (read-string "Task id: ")
         (completing-read "Agent: " '("claude" "codex" "agy") nil t)))
  (let* ((task (gethash task-id sarathi--tasks))
         (profile (sarathi--task-profile task-id))
         (process-environment (sarathi--profile-environment profile))
         (payload (sarathi--cli-json "agent-command" task-id agent "--json"))
         (command (alist-get 'command payload))
         (title (or (plist-get task :title) "task"))
         (buffer-name (sarathi--agent-buffer-name agent task-id title))
         (buffer (get-buffer-create buffer-name)))
    (unless command (error "Sarathi returned no agent command"))
    (apply #'make-comint-in-buffer buffer-name buffer (car command) nil (cdr command))
    (with-current-buffer buffer
      (setq-local sarathi-task-id task-id)
      (setq-local sarathi-agent agent))
    (pop-to-buffer buffer)
    (message "Started %s in %s profile without keystroke injection" agent profile)))

(defun sarathi-rename-task (task-id title)
  "Manually rename TASK-ID to TITLE and lock automatic naming."
  (interactive "sTask id: \nsNew title: ")
  (let* ((profile (sarathi--task-profile task-id))
         (process-environment (sarathi--profile-environment profile))
         (payload (sarathi--cli-json "rename" task-id title))
         (new-title (alist-get 'title payload))
         (label (sarathi--label task-id new-title)))
    (tab-bar-rename-tab label)
    (puthash task-id (plist-put (gethash task-id sarathi--tasks) :title new-title)
             sarathi--tasks)
    (sarathi--rename-agent-buffers task-id new-title)
    (rename-frame (selected-frame) label)
    (set-frame-parameter (selected-frame) 'title label)
    (message "Sarathi renamed task to %s" new-title)))

(defun sarathi-capture (task-id kind summary)
  "Capture a derived evidence SUMMARY of KIND for TASK-ID."
  (interactive
   (list (read-string "Task id: ")
         (completing-read "Kind: " '("change" "solution" "workaround" "learning" "decision" "feedback" "result") nil t)
         (read-string "Derived summary (no raw terminal/source content): ")))
  (let* ((profile (sarathi--task-profile task-id))
         (process-environment (sarathi--profile-environment profile)))
    (sarathi--cli-json "capture" task-id kind summary))
  (message "Evidence captured"))

(defun sarathi-complete-task (task-id approach result workarounds workflow commands learnings links)
  "Complete TASK-ID after synchronously recording its reusable resolution."
  (interactive
   (list (read-string "Task id: ")
         (read-string "How did you get it working? ")
         (read-string "What was the result? ")
         (read-string "Workarounds (semicolon separated): ")
         (read-string "Debug/workflow steps (semicolon separated): ")
         (read-string "Redacted command summaries (semicolon separated): ")
         (read-string "Learnings (semicolon separated): ")
         (read-string "Confluence/runbook/artifact links (semicolon separated): ")))
  (let* ((profile (sarathi--task-profile task-id))
         (process-environment (sarathi--profile-environment profile)))
    (apply #'sarathi--cli-json
           (append
            (list "complete" task-id "--approach" approach "--result" result)
            (sarathi--flagged-values "--workaround" (sarathi--split-values workarounds))
            (sarathi--flagged-values "--workflow-step" (sarathi--split-values workflow))
            (sarathi--flagged-values "--command-summary" (sarathi--split-values commands))
            (sarathi--flagged-values "--learning" (sarathi--split-values learnings))
            (sarathi--flagged-values "--link" (sarathi--split-values links)))))
  (message "Task completed with an immediate resolution record"))

(defun sarathi-restore (profile)
  "Restore PROFILE's registered workspaces after daemon restart."
  (interactive (list (completing-read "Profile: " '("personal" "work" "neutral") nil t)))
  (let* ((process-environment (sarathi--profile-environment profile))
         (tasks (sarathi--cli-json "list" "--json")))
    (dolist (task (reverse tasks))
      (sarathi-open-task (alist-get 'id task)
                         (alist-get 'workspace task)
                         (alist-get 'title task)
                         (alist-get 'profile task)))))

(provide 'sarathi)
;;; sarathi.el ends here
