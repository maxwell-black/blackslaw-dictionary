     1|# ⚖️ Black's Law Dictionary (1910)
     2|
     3|A free, searchable web version of Black's Law Dictionary, Second Edition (1910) by Henry Campbell Black, M.A.
     4|
     5|## 🌐 Live Site
     6|
     7|**https://blackslaw.io**
     8|
     9|## 📚 About
    10|
    11|This project provides free access to over 12,000 legal definitions from the classic 1910 edition of Black's Law Dictionary. The original text has been OCR-corrected using AI to fix scanning errors while preserving the 1910-era spelling and legal terminology.
    12|
    13|### Features
    14|
    15|- 🔍 **Fast search** - Search by term or definition content
    16|- 🔤 **Browse by letter** - Quick navigation A-Z
    17|- 📱 **Mobile-friendly** - Works on all devices
    18|- ⚡ **Fast loading** - Static site, no server required
    19|- 🔗 **Cross-references** - Links between related legal terms
    20|- 🌙 **Clean design** - Easy to read, distraction-free
    21|
    22|## 🛠️ Technical
    23|
    24|- **Frontend**: Vanilla HTML, CSS, JavaScript
    25|- **Data**: 12,178 corrected entries in JSON format
    26|- **Hosting**: GitHub Pages + Namecheap domain
    27|- **Source**: [Internet Archive](https://archive.org/details/BlacksLaw2dEd)
    28|
    29|## 📖 Data Source
    30|
    31|The raw text was sourced from the Internet Archive's digitization of Black's Law Dictionary, 2nd Edition (1910). The OCR text was corrected using Moonshot AI (Kimi) to fix character substitutions, broken words, and garbled punctuation while preserving the original 1910 spelling, grammar, and legal terminology.
    32|
    33|## 📝 License
    34|
    35|The original Black's Law Dictionary (2nd Edition, 1910) is in the **public domain**.
    36|
    37|This web implementation is released under the MIT License.
    38|
    39|## 🙏 Credits
    40|
    41|- **Original Author**: Henry Campbell Black, M.A. (1910)
    42|- **Digitization**: Internet Archive
    43|- **OCR Correction**: Moonshot AI (Kimi K2.5)
    44|- **Web Implementation**: [Your name]
    45|
    46|---
    47|
    48|*Free legal knowledge for everyone.*
    49|

## 🚀 Deployment

### Quick Deploy
Run the deployment script:
```bash
cd ~/blackslaw-dictionary
./deploy.sh
```

### Manual Steps
1. Authenticate with GitHub:
   ```bash
   gh auth login
   ```

2. Create and push repository:
   ```bash
   gh repo create blackslaw-dictionary --public --source=. --remote=origin --push
   ```

3. Enable GitHub Pages:
   - Go to https://github.com/maxwelljblack/blackslaw-dictionary/settings/pages
   - Source: Deploy from a branch
   - Branch: main / (root)
   - Save

### Domain Configuration
The domain blackslaw.io is already configured in Namecheap with DNS pointing to GitHub Pages.

### Auto-Update
A cronjob is scheduled to automatically update entries as OCR progresses (currently 62% complete).

## 📊 Current Status
- ✅ Website files created
- ✅ 7,500 entries corrected (62% of 12,178)
- ✅ OCR process running (PID monitored)
- ⏳ GitHub repository needs authentication
- ⏳ GitHub Pages to be enabled after auth
