# ERNEST Website Repository

Welcome to the official repository for the **ERNEST (European Researchers' Night Escape Science Team)** website. 

This repository contains the HTML, CSS, and asset files that power the website. This guide explains how team members can easily update site content—such as adding new escape rooms, updating partner descriptions, or adding team members—directly from their web browser, without needing to install any coding software.

---

## 🛠️ How to Edit Files Directly on GitHub (Browser)

If you spot a typo or need to update text, you can do it right here on GitHub in just a few clicks.
Currently we will use two branches of the code:
- `test` --> used to make changes and test the website before deploying it to the official website. You can see the results of the changes in `test` on https://ernest-project.webtest.cern.ch/ERNESTWeb_test/ (Note: it is updated every 5 minutes)
- `main` --> contains the official website that is currently online at https://www.ernest-project.eu
To propagate the changes from the `test` to `main` (ie. to https://www.ernest-project.eu) you will make a pull request (see Step 6)

### Step 1: Select the Correct Branch (test)
1. Navigate to the [repository page on the `test` branch](../tree/test).
2. In the top-left corner, just above the list of files, look for the branch dropdown menu and ensure **`test`** is selected (instead of `main`). 

### Step 2: Open the File
Click on the name of the file you want to edit. For example:
* `index.html` - To edit the homepage, project description, or partner list.
* `escape-rooms.html` - To update or add new escape rooms to the catalogue.
* `network.html` - To update team members or institutional roles.

### Step 3: Enter Edit Mode
Once the file is open, click the **Pencil icon ✏️** in the top right corner of the file viewer. This will open the in-browser text editor.

### Step 4: Make Your Changes
Make your necessary text edits within the HTML. 

### Step 5: Save (Commit) Your Changes
1. Once you are happy with your edits, click the green **Commit changes...** button in the top right corner.
2. A dialog box will appear. In the first text box, write a brief, descriptive message explaining what you changed (e.g., *"Added the Gravity Lab escape room"* or *"Fixed a typo in the About section"*).
3. Make sure the option **"Commit directly to the `test` branch"** is selected.
4. Click the green **Commit changes** button to finalize your edit.
5. Your changes should be visible on https://ernest-project.webtest.cern.ch/ERNESTWeb_test/ within 5 minutes.

### Step 6: Deploy Online of Your changes
1. Wait 5 minutes and check that the test website (https://ernest-project.webtest.cern.ch/ERNESTWeb_test/) looks ok.
2. Make a Pull Request from `test` to `main`: simply click on https://github.com/matteo-bauce/ERNESTWeb/compare/main...test?expand=1
3. Put a Title and a Description
4. Check the changed files correspond to your changes
5. Push on the green button "Create pull request"
6. Once the pull request is create, the browser will open the pull request page. After a couple of minutes you should get the Copilot AID review. You can click on the green button "Commit suggestion" and then "Apply suggestion" to accept Copilot suggestions.
7. To merge it simply push on the pull "Merge pull request" from the Pull Request page (*).
8. Check that your changes are online on www.ernest-project.eu

 (*) If you closed by mistake the pull request page, you can find it from https://github.com/matteo-bauce/ERNESTWeb/pulls

Important: if you create a pull request and you do not merge it, all the changes applied on `test` branch will be automatically included in your pull request

Your changes are now saved to the repository in the branch `main` and they should be online on www.ernest-project.eu .

---

## Website analytics and public visit counter

The website uses [GoatCounter](https://www.goatcounter.com/) for privacy-friendly analytics and for the public visit counter displayed in the footer. GoatCounter is configured in `site.js` with the site code:

```js
const GOATCOUNTER_CODE = "ernest-project";
```

This points to the GoatCounter dashboard at:

https://ernest-project.goatcounter.com

GoatCounter should be used only for aggregate website statistics and the public visit counter. It must not be used for marketing, profiling, or cross-site tracking. The cookie policy pages in English, Italian, and French describe this use.

When maintaining the counter, check the following in GoatCounter:

1. The account email is verified.
2. The public visitor counter is enabled in the site settings. The setting is called **Allow adding visitor counts on your website**.

Do not commit GoatCounter passwords or recovery information to this repository. Store credentials only in the project’s approved password manager or shared credential storage.


#### Expert links
- GitLab pipelines: https://gitlab.cern.ch/sdonato/ERNESTWeb/-/pipelines (used to update ernest-project.webtest.cern.ch)
- GitLab mirroring: https://gitlab.cern.ch/sdonato/ERNESTWeb/-/settings/repository#js-push-remote-settings
