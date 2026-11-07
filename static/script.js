// THUMBNAIL ANALYZER
const form = document.getElementById("uploadForm");
const input = document.getElementById("thumbnail");
const preview = document.getElementById("previewContainer");
const previewImage = document.getElementById("previewImage");
const button = document.getElementById("analyzeBtn");
const status = document.getElementById("status");

if (input) {
    input.addEventListener("change", () => {
        const file = input.files[0];
        if (!file) return;
        previewImage.src = URL.createObjectURL(file);
        preview.style.display = "block";
    });
}

if (form) {
    form.addEventListener("submit", async (e) => {
        e.preventDefault();
        const file = input.files[0];
        if (!file) {
            status.textContent = "Select an image first.";
            return;
        }

        const formData = new FormData();
        formData.append("thumbnail", file);
        button.disabled = true;
        button.textContent = "Analyzing...";
        status.textContent = "Please wait...";

        try {
            const response = await fetch("/api/analyze", {method: "POST",body: formData});
            const data = await response.json();
            if (!response.ok || data.error) {throw new Error(data.error || "Analysis failed");}
            const image = data.image_analysis || {};
            document.getElementById("resolution").textContent = image.resolution || "—";
            document.getElementById("brightness").textContent = image.brightness || "—";
            document.getElementById("contrast").textContent = image.contrast || "—";
            document.getElementById("aspectRatio").textContent = image.aspect_ratio || "—";
            document.getElementById("qualityScore").textContent = (image.quality_score ?? "—") + "/100";
            document.getElementById("imageAnalysis").textContent = JSON.stringify(image, null, 2);
            document.getElementById("aiAnalysis").innerHTML = marked.parse(data.ai_analysis ||"No AI analysis available.");
            
            const text = data.text_analysis || {};
            document.getElementById("textDetected").textContent = text.text_detected ? "Detected" : "Not Found";
            document.getElementById("detectedText").textContent = text.extracted_text || "No text detected.";

            const ctr = data.ctr_prediction || {};
            document.getElementById("clickProbability").textContent = (ctr.click_probability ?? "--") + "%";
            document.getElementById("engagementPotential").textContent = (ctr.engagement_potential ?? "--") + "%";
            document.getElementById("predictedCTR").textContent = (ctr.predicted_ctr_score ?? "--") + "/100";
            document.getElementById("ctrMessage").textContent = ctr.message || "No CTR prediction available.";

            const heatmap = data.heatmap_analysis || {};
            document.getElementById("heatmapImage").src = heatmap.heatmap_url || "";
            document.getElementById("attentionArea").textContent = heatmap.attention_area || "--";
            document.getElementById("hotspots").textContent = heatmap.hotspots || "--";
            document.getElementById("deadZones").textContent = heatmap.dead_zones || "--";
            document.getElementById("subjectFocus").textContent = heatmap.subject_focus || "--";
            status.textContent = "Analysis completed successfully!";
        } catch (error) {
            status.textContent = "Error: " + error.message;
            console.error(error);
        } finally {
            button.disabled = false;
            button.textContent = "Analyze Thumbnail →";
        }
    });
}

// USER IMAGE PREVIEW
const personImage = document.getElementById("personImage");
const personPreview = document.getElementById("personPreview");
const personPreviewImage = document.getElementById("personPreviewImage");
const personFileName = document.getElementById("personFileName");

if (personImage) {
    personImage.addEventListener("change", () => {
        const file = personImage.files[0];
        if (!file) {
            personPreview.style.display = "none";
            personFileName.textContent = "Choose your image";
            return;
        }
        personPreviewImage.src = URL.createObjectURL(file);
        personPreview.style.display = "block";
        personFileName.textContent = file.name;
    });
}

// AI THUMBNAIL BUILDER
// CLOUDFLARE FLUX + USER IMAGE + PILLOW TEXT
const promptForm = document.getElementById("promptForm");
if (promptForm) {
    promptForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        const prompt = document.getElementById("thumbnailPrompt").value.trim();
        const personFile = document.getElementById("personImage").files[0];
        const headline = document.getElementById("headlineText").value.trim();
        const fontSize = document.getElementById("fontSize").value;
        const textColor = document.getElementById("textColor").value;
        const position = document.getElementById("textPosition").value;
        const aspectRatio = document.getElementById("imageRatio").value;
        const button = document.getElementById("generatePromptBtn");
        const status = document.getElementById("promptStatus");

        if (!prompt) {
            status.textContent = "Please enter a thumbnail description.";
            return;
        }
        
        button.disabled = true;
        button.textContent = "Generating...";
        document.getElementById("promptPreview").style.display = "none";

        const emptyPreview = document.getElementById("emptyPreview");
        if (emptyPreview) {emptyPreview.style.display = "flex";}
        status.textContent = "AI is creating your thumbnail...";

        try {
            // STEP 1 - GENERATE AI IMAGE WITH CLOUDFLARE
            const generateResponse = await fetch(
                "/api/generate-thumbnail",
                {
                    method: "POST",
                    headers: { "Content-Type": "application/json"},
                    body: JSON.stringify({prompt: prompt,aspect_ratio: aspectRatio})
                }
            );

            const generatedData = await generateResponse.json();
            if (!generateResponse.ok ||generatedData.error) {
                throw new Error(generatedData.error ||"AI generation failed");
            }
            console.log("Cloudflare image generated:",generatedData.image_url);
            status.textContent = "AI image created. Building final thumbnail...";

            // STEP 2 - DOWNLOAD GENERATED AI IMAGE
            const imageResponse = await fetch(generatedData.image_url);
            if (!imageResponse.ok) {
                throw new Error("Could not load generated image.");
            }
            const imageBlob = await imageResponse.blob();
            const generatedFile = new File([imageBlob],"ai-thumbnail.jpg",{type: imageBlob.type || "image/jpeg"});

            // STEP 3 - SEND AI IMAGE + USER IMAGE + TEXT
            // TO /api/build
            const buildFormData = new FormData();
            buildFormData.append("thumbnail",generatedFile);
            if (personFile) {buildFormData.append("person",personFile);}
            buildFormData.append("text", headline);
            buildFormData.append("font_size", fontSize);
            buildFormData.append("text_color",textColor);
            buildFormData.append("position", position
);

buildFormData.append("prompt", prompt);
buildFormData.append("aspect_ratio", aspectRatio);

            // STEP 4 - BUILD FINAL THUMBNAIL
            const buildResponse = await fetch("/api/build",{ method: "POST", body: buildFormData});
            const builtData = await buildResponse.json();
            if (!buildResponse.ok || builtData.error) {
                throw new Error(builtData.error || "Thumbnail building failed");
            }

            // STEP 5 - SHOW FINAL THUMBNAIL
            document.getElementById("promptImage").src = builtData.image_url;
            document.getElementById("promptDownload").href = builtData.image_url;
            document.getElementById("promptPreview").style.display = "block";

            const emptyPreview = document.getElementById("emptyPreview");

            if (emptyPreview) { emptyPreview.style.display = "none";}
            status.textContent = "Thumbnail generated successfully!";
            } catch (error) {
            status.textContent = "Error: " + error.message;
            console.error( "Thumbnail Builder Error:", error);
        } finally {
            button.disabled = false;
            button.textContent = "✦ Generate Thumbnail with AI";
        }
    });
}

// PROMPT EXAMPLES
function setPrompt(text) {
    const prompt = document.getElementById("thumbnailPrompt");
    if (prompt) {prompt.value = text;}
}