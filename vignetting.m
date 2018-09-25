%function vignetting(fPath)
clear, close all 

% unimportant warning that 
warning('off','MATLAB:imagesci:tifftagsread:badTagValueDivisionByZero')

folder = "F:\Data\apacker\2018-09-25\2018-09-25_Vignetting_s-003";
tif_list = dir(fullfile(folder, '*.tif'));




for i = 1:length(tif_list)
    
    disp(['channel ' num2str(i) ' is the file named ' tif_list(i).name]) 
    
    fPath = [tif_list(i).folder '\' tif_list(i).name];
       
    im_matrix = importdata(fPath);

    im_shape = size(im_matrix);
    width = im_shape(1);

    centre = floor(width * 0.5);

    line_upper = centre + 15;
    line_lower = centre - 15;

    height_line = im_matrix(:, line_lower:line_upper);
    width_line =  im_matrix(line_lower:line_upper,:);
    
    width_mean = mean(width_line, 1);
    height_mean = mean(height_line, 2);

    figure
    plot(width_mean)
    title(['hortizonal line CH' num2str(i)])

    figure
    plot(height_mean)
    title(['vertical line CH' num2str(i)])
    
    % calculate the vignetting as peak dividded by 10th value from
    % left or right, whichever is smallest
    
    width_min = min([width_mean(10), width_mean(end-10)]);
    height_min = min([height_mean(10), height_mean(end-10)]);
    
    width_vig = 100 - ((width_min / max(width_mean)) * 100);
    height_vig = 100 - ((height_min / max(height_mean)) * 100);
    
    disp(['vertical vignetting for channel ' num2str(i) ' is ' num2str(height_vig) ' percent']) 
    disp(['horizontal vignetting for channel ' num2str(i) ' is ' num2str(width_vig) ' percent']) 
    


end

warning('off','MATLAB:imagesci:tifftagsread:badTagValueDivisionByZero')
