clear
fPath = '/home/jamesrowland/Desktop/2018-12-17_J023_z-002.tif';


stack = TiffReader(fPath);

%the slice to start at, use this to cut off layer 1 stuff
start_slice = 6;

close all, figure

slice_size = zeros(size(stack,3),1);

for slice = start_slice:size(stack,3)
    
    im = double(stack(:,:,slice));
    
    [x,y,normImg] = MariusCellFinder(im);
    
    if isempty(x)
        disp(['no cells found for slice ' num2str(slice)])
        continue
    end
    
    centroids = zeros(512,512);
    
    num_steps = 15;
    
    across_units = [];
    
    for unit = 1:length(x)
        
        mean_pix = [];
        
        x_coord = y(unit);
        y_coord = x(unit);
        
        if x_coord + num_steps > 512 || y_coord + num_steps > 512 || x_coord - num_steps < 1 || y_coord - num_steps < 1
            disp('cell too close to edge')
            continue
        end
        
        centroids(x_coord, y_coord) = 1;
        
        
        for diameter = 1:num_steps
            
            square = get_square(diameter);
            x_offset = square(1,:) + x_coord;
            y_offset = square(2,:) + y_coord;
            try
                pixels = im(x_offset,y_offset);
            catch
                keyboard
            end
            
            mean_pix(diameter) = mean(pixels(:));
            
        end
        
        %add the centre
        mean_pix = [im(x_coord, y_coord), mean_pix];
        
        across_units(unit,:) = mean_pix;
        
    end
    
    imwrite(centroids, strcat('/home/jamesrowland/Desktop/centroids/centroids_',num2str(slice),'.tiff'));
    
    
    grand_average = mean(across_units,1);
    
    
    [xData, yData] = prepareCurveData( [], grand_average );
    
    % fit the gradn average with the sum of 2 gaussians
    ft = fittype( 'gauss2' );
    opts = fitoptions( 'Method', 'NonlinearLeastSquares' );
    
    opts.Lower = [-Inf -Inf 0 -Inf -Inf 0];
    opts.StartPoint = [163.562610229277 4 2.37901958278891 119.99787320785 14 5.67806346205408];
    
    % Fit model to data.
    [fitresult, gof] = fit( xData, yData, ft, opts );

    surrogate_x = linspace(min(xData),max(xData), 100);
    yFitted = feval(fitresult,surrogate_x);
    
    % Plot fit with data.
    hold on
    subplot(6,6,slice)
    plot(surrogate_x,yFitted);
    plot(grand_average, 'o');
    hold off
    %legend( h, 'data', 'fit', 'Location', 'NorthEast' );
    ylabel('pixel_intensity')
    xlabel('distance from centre (pixels)')
    
    disp(['R squared of fit is ' num2str(gof.rsquare)])
    
    
    % cell size can be approximated by full width half max of gaussian 1
    size_approx = 2.355 * fitresult.c1;
    
    disp(['cell size is approx ', num2str(2*size_approx)])
    
    dim = [.55 .55 .3 .3];
    str = ['R squared of fit is ' num2str(gof.rsquare) newline 'Cell size is approx ', num2str(2*size_approx)];
    annotation('textbox',dim,'String',str,'FitBoxToText','on', 'VerticalAlignment', 'bottom', 'HorizontalAlignment', 'Right');
    if gof.rsquare > 0.9
        slice_size(slice) = 2*size_approx;
    end
    
end

close all, figure

%20um step size in this case
x_axis = (1:length(slice_size))*20;
plot(x_axis,slice_size,'o');
ylim([10,18]);
save('slice_size.mat', 'slice_size');
% 
